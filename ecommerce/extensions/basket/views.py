from __future__ import absolute_import, unicode_literals

import logging
from datetime import datetime
from decimal import Decimal

import dateutil.parser
import newrelic.agent
import waffle
from django.http import HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.utils.html import escape
from django.utils.translation import ugettext as _
from opaque_keys.edx.keys import CourseKey
from oscar.apps.basket.views import VoucherAddView as BaseVoucherAddView
from oscar.apps.basket.views import *  # pylint: disable=wildcard-import, unused-wildcard-import
from oscar.core.prices import Price
from requests.exceptions import ConnectionError, Timeout
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from six.moves import range, zip
from six.moves.urllib.parse import urlencode
from slumber.exceptions import SlumberBaseException

from ecommerce.core.exceptions import SiteConfigurationError
from ecommerce.core.url_utils import get_lms_course_about_url, get_lms_url
from ecommerce.courses.utils import get_certificate_type_display_value, get_course_info_from_catalog
from ecommerce.enterprise.entitlements import get_enterprise_code_redemption_redirect
from ecommerce.enterprise.utils import CONSENT_FAILED_PARAM, get_enterprise_customer_from_voucher, has_enterprise_offer
from ecommerce.extensions.analytics.utils import (
    prepare_analytics_data,
    track_segment_event,
    translate_basket_line_for_segment
)
from ecommerce.extensions.basket.constants import EMAIL_OPT_IN_ATTRIBUTE
from ecommerce.extensions.basket.utils import (
    add_utm_params_to_url,
    apply_voucher_on_basket_and_check_discount,
    get_basket_switch_data,
    prepare_basket,
    validate_voucher
)
from ecommerce.extensions.offer.utils import format_benefit_value, render_email_confirmation_if_required
from ecommerce.extensions.order.exceptions import AlreadyPlacedOrderException
from ecommerce.extensions.partner.shortcuts import get_partner_for_site
from ecommerce.extensions.payment.constants import (
    CLIENT_SIDE_CHECKOUT_FLAG_NAME,
    ENABLE_MICROFRONTEND_FOR_BASKET_PAGE_FLAG_NAME
)
from ecommerce.extensions.payment.forms import PaymentForm

BasketAttribute = get_model('basket', 'BasketAttribute')
BasketAttributeType = get_model('basket', 'BasketAttributeType')
Benefit = get_model('offer', 'Benefit')
logger = logging.getLogger(__name__)
Product = get_model('catalogue', 'Product')
StockRecord = get_model('partner', 'StockRecord')
Voucher = get_model('voucher', 'Voucher')


def _redirect_to_payment_microfrontend_if_configured(request):
    if waffle.flag_is_active(request, ENABLE_MICROFRONTEND_FOR_BASKET_PAGE_FLAG_NAME):
        if (
                request.site.siteconfiguration.enable_microfrontend_for_basket_page and
                request.site.siteconfiguration.payment_microfrontend_url
        ):
            url = add_utm_params_to_url(
                request.site.siteconfiguration.payment_microfrontend_url,
                list(request.GET.items()),
            )
            return HttpResponseRedirect(url)
    return None


class BasketAddItemsView(View):
    """
    View that adds multiple products to a user's basket.
    An additional coupon code can be supplied so the offer is applied to the basket.
    """

    def get(self, request):
        partner = get_partner_for_site(request)

        skus = [escape(sku) for sku in request.GET.getlist('sku')]
        code = request.GET.get('code', None)

        if not skus:
            return HttpResponseBadRequest(_('No SKUs provided.'))

        products = Product.objects.filter(stockrecords__partner=partner, stockrecords__partner_sku__in=skus)
        if not products:
            return HttpResponseBadRequest(_('Products with SKU(s) [{skus}] do not exist.').format(skus=', '.join(skus)))

        logger.info('Starting payment flow for user[%s] for products[%s].', request.user.username, skus)

        voucher = Voucher.objects.get(code=code) if code else None

        if voucher is None:
            # If there is an Enterprise entitlement available for this basket,
            # we redirect to the CouponRedeemView to apply the discount to the
            # basket and handle the data sharing consent requirement.
            code_redemption_redirect = get_enterprise_code_redemption_redirect(
                request,
                products,
                skus,
                'basket:basket-add'
            )
            if code_redemption_redirect:
                return code_redemption_redirect

        # check availability of products
        unavailable_product_ids = []
        for product in products:
            purchase_info = request.strategy.fetch_for_product(product)
            if not purchase_info.availability.is_available_to_buy:
                logger.warning('Product [%s] is not available to buy.', product.title)
                unavailable_product_ids.append(product.id)

        available_products = products.exclude(id__in=unavailable_product_ids)
        if not available_products:
            msg = _('No product is available to buy.')
            return HttpResponseBadRequest(msg)

        # Associate the user's email opt in preferences with the basket in
        # order to opt them in later as part of fulfillment
        BasketAttribute.objects.update_or_create(
            basket=request.basket,
            attribute_type=BasketAttributeType.objects.get(name=EMAIL_OPT_IN_ATTRIBUTE),
            defaults={'value_text': request.GET.get('email_opt_in') == 'true'},
        )

        try:
            prepare_basket(request, available_products, voucher)
        except AlreadyPlacedOrderException:
            return render(request, 'edx/error.html', {'error': _('You have already purchased these products')})

        if self._is_single_course_purchase(products):
            redirect_response = _redirect_to_payment_microfrontend_if_configured(request)
            if redirect_response:
                return redirect_response

        url = add_utm_params_to_url(reverse('basket:summary'), list(self.request.GET.items()))
        return HttpResponseRedirect(url, status=303)

    def _is_single_course_purchase(self, products):
        return len(products) == 1 and products[0].is_seat_product


class BasketLogicMixin(object):
    """
    Business logic for determining basket contents and checkout/payment options.
    """

    @newrelic.agent.function_trace()
    def _determine_product_type(self, product):
        """
        Return the seat type based on the product class
        """
        seat_type = None
        if product.is_seat_product or product.is_course_entitlement_product:
            seat_type = get_certificate_type_display_value(product.attr.certificate_type)
        elif product.is_enrollment_code_product:
            seat_type = get_certificate_type_display_value(product.attr.seat_type)
        return seat_type

    @newrelic.agent.function_trace()
    def _deserialize_date(self, date_string):
        date = None
        try:
            date = dateutil.parser.parse(date_string)
        except (AttributeError, ValueError, TypeError):
            pass
        return date

    @newrelic.agent.function_trace()
    def _get_course_data(self, product):
        """
        Return course data.

        Args:
            product (Product): A product that has course_key as attribute (seat or bulk enrollment coupon)
        Returns:
            Dictionary containing course name, course key, course image URL and description.
        """
        if product.is_seat_product:
            course_key = CourseKey.from_string(product.attr.course_key)
        else:
            course_key = None
        course_name = None
        image_url = None
        short_description = None
        course_start = None
        course_end = None
        course = None

        try:
            course = get_course_info_from_catalog(self.request.site, product)
            try:
                image_url = course['image']['src']
            except (KeyError, TypeError):
                image_url = ''
            short_description = course.get('short_description', '')
            course_name = course.get('title', '')

            # The course start/end dates are not currently used
            # in the default basket templates, but we are adding
            # the dates to the template context so that theme
            # template overrides can make use of them.
            course_start = self._deserialize_date(course.get('start'))
            course_end = self._deserialize_date(course.get('end'))
        except (ConnectionError, SlumberBaseException, Timeout):
            logger.exception('Failed to retrieve data from Discovery Service for course [%s].', course_key)

        if self.request.basket.num_items == 1 and product.is_enrollment_code_product:
            course_key = CourseKey.from_string(product.attr.course_key)
            if course and course.get('marketing_url', None):
                course_about_url = course['marketing_url']
            else:
                course_about_url = get_lms_course_about_url(course_key=course_key)
            messages.info(
                self.request,
                _(
                    '{strong_start}Purchasing just for yourself?{strong_end}{paragraph_start}If you are '
                    'purchasing a single code for someone else, please continue with checkout. However, if you are the '
                    'learner {link_start}go back{link_end} to enroll directly.{paragraph_end}'
                ).format(
                    strong_start='<strong>',
                    strong_end='</strong>',
                    paragraph_start='<p>',
                    paragraph_end='</p>',
                    link_start='<a href="{course_about}">'.format(course_about=course_about_url),
                    link_end='</a>'
                ),
                extra_tags='safe'
            )

        return {
            'product_title': course_name,
            'course_key': course_key,
            'image_url': image_url,
            'product_description': short_description,
            'course_start': course_start,
            'course_end': course_end,
        }

    @newrelic.agent.function_trace()
    def _process_basket_lines(self, lines):
        """Processes the basket lines and extracts information for the view's context.
        In addition determines whether:
            * verification message should be displayed
            * voucher form should be displayed
            * switch link (for switching between seat and enrollment code products) should be displayed
        and returns that information for the basket view context to be updated with it.

        Args:
            lines (list): List of basket lines.
        Returns:
            context_updates (dict): Containing information with which the context needs to
                                    be updated with.
            lines_data (list): List of information about the basket lines.
        """
        display_verification_message = False
        lines_data = []
        show_voucher_form = True
        is_enrollment_code_purchase = False
        switch_link_text = partner_sku = order_details_msg = None

        for line in lines:
            if line.product.is_seat_product or line.product.is_course_entitlement_product:
                line_data = self._get_course_data(line.product)
                certificate_type = line.product.attr.certificate_type

                if getattr(line.product.attr, 'id_verification_required', False) and certificate_type != 'credit':
                    display_verification_message = True

                if line.product.is_course_entitlement_product:
                    order_details_msg = _(
                        'After you complete your order you will be able to select course dates from your dashboard.'
                    )
                else:
                    if certificate_type == 'verified':
                        order_details_msg = _(
                            'After you complete your order you will be automatically enrolled '
                            'in the verified track of the course.'
                        )
                    elif certificate_type == 'credit':
                        order_details_msg = _('After you complete your order you will receive credit for your course.')
                    else:
                        order_details_msg = _(
                            'After you complete your order you will be automatically enrolled in the course.'
                        )
            elif line.product.is_enrollment_code_product:
                line_data = self._get_course_data(line.product)
                is_enrollment_code_purchase = True
                show_voucher_form = False
                order_details_msg = _(
                    '{paragraph_start}By purchasing, you and your organization agree to the following terms:'
                    '{paragraph_end} {ul_start} {li_start}Each code is valid for the one course covered and can be '
                    'used only one time.{li_end} '
                    '{li_start}You are responsible for distributing codes to your learners in your organization.'
                    '{li_end} {li_start}Each code will expire in one year from date of purchase or, if earlier, once '
                    'the course is closed.{li_end} {li_start}If a course is not designated as self-paced, you should '
                    'confirm that a course run is available before expiration. {li_end} {li_start}You may not resell '
                    'codes to third parties.{li_end} '
                    '{li_start}All edX for Business Sales are final and not eligible for refunds.{li_end}{ul_end} '
                    '{paragraph_start}You will receive an email at {user_email} with your enrollment code(s). '
                    '{paragraph_end}'
                ).format(
                    paragraph_start='<p>',
                    paragraph_end='</p>',
                    ul_start='<ul>',
                    li_start='<li>',
                    li_end='</li>',
                    ul_end='</ul>',
                    user_email=self.request.user.email
                )
            else:
                line_data = {
                    'product_title': line.product.title,
                    'image_url': None,
                    'product_description': line.product.description
                }

            # Get variables for the switch link that toggles from enrollment codes and seat.
            switch_link_text, partner_sku = get_basket_switch_data(line.product)

            if line.has_discount:
                benefit = list(self.request.basket.applied_offers().values())[0].benefit
                benefit_value = format_benefit_value(benefit)
            else:
                benefit_value = None

            line_data.update({
                'sku': line.product.stockrecords.first().partner_sku,
                'benefit_value': benefit_value,
                'enrollment_code': line.product.is_enrollment_code_product,
                'line': line,
                'seat_type': self._determine_product_type(line.product),
            })
            lines_data.append(line_data)

        context_updates = {
            'display_verification_message': display_verification_message,
            'order_details_msg': order_details_msg,
            'partner_sku': partner_sku,
            'show_voucher_form': show_voucher_form,
            'switch_link_text': switch_link_text,
            'is_enrollment_code_purchase': is_enrollment_code_purchase
        }

        return context_updates, lines_data

    @newrelic.agent.function_trace()
    def _get_payment_processors_data(self, payment_processors):
        """Retrieve information about payment processors for the client side checkout basket.

        Args:
            payment_processors (list): List of all available payment processors.
        Returns:
            A dictionary containing information about the payment processor(s) with which the
            basket view context needs to be updated with.
        """
        site_configuration = self.request.site.siteconfiguration
        payment_processor_class = site_configuration.get_client_side_payment_processor_class()

        if payment_processor_class:
            payment_processor = payment_processor_class(self.request.site)
            current_year = datetime.today().year

            return {
                'client_side_payment_processor': payment_processor,
                'enable_client_side_checkout': True,
                'months': list(range(1, 13)),
                'payment_form': PaymentForm(
                    user=self.request.user,
                    request=self.request,
                    initial={'basket': self.request.basket},
                    label_suffix=''
                ),
                'paypal_enabled': 'paypal' in (p.NAME for p in payment_processors),
                # Assumption is that the credit card duration is 15 years
                'years': list(range(current_year, current_year + 16)),
            }
        else:
            msg = 'Unable to load client-side payment processor [{processor}] for ' \
                  'site configuration [{sc}]'.format(processor=site_configuration.client_side_payment_processor,
                                                     sc=site_configuration.id)
            raise SiteConfigurationError(msg)

    @newrelic.agent.function_trace()
    def get_basket_context_data(self, context):
        formset = context.get('formset', [])
        lines = context.get('line_list', [])
        site_configuration = self.request.site.siteconfiguration

        failed_enterprise_consent_code = self.request.GET.get(CONSENT_FAILED_PARAM)
        if failed_enterprise_consent_code:
            messages.error(
                self.request,
                _("Could not apply the code '{code}'; it requires data sharing consent.").format(
                    code=failed_enterprise_consent_code
                )
            )

        context_updates, lines_data = self._process_basket_lines(lines)
        context.update(context_updates)

        user = self.request.user
        context.update({
            'analytics_data': prepare_analytics_data(
                user,
                site_configuration.segment_key,
            ),
            'enable_client_side_checkout': False,
            'sdn_check': site_configuration.enable_sdn_check
        })

        payment_processors = site_configuration.get_payment_processors()
        if site_configuration.client_side_payment_processor \
                and waffle.flag_is_active(self.request, CLIENT_SIDE_CHECKOUT_FLAG_NAME):
            payment_processors_data = self._get_payment_processors_data(payment_processors)
            context.update(payment_processors_data)

        # Total benefit displayed in price summary.
        # Currently only one voucher per basket is supported.
        try:
            applied_voucher = self.request.basket.vouchers.first()
            total_benefit = (
                format_benefit_value(applied_voucher.best_offer.benefit)
                if applied_voucher else None
            )
        except ValueError:
            total_benefit = None
        num_of_items = self.request.basket.num_items
        context.update({
            'formset_lines_data': list(zip(formset, lines_data)),
            # the new payment api is not using the formset, so the zip above doesn't work
            'lines_data': lines_data,
            'free_basket': context['order_total'].incl_tax == 0,
            'homepage_url': get_lms_url(''),
            'min_seat_quantity': 1,
            'max_seat_quantity': 100,
            'payment_processors': payment_processors,
            'total_benefit': total_benefit,
            'line_price': (self.request.basket.total_incl_tax_excl_discounts / num_of_items) if num_of_items > 0 else 0,
            'lms_url_root': site_configuration.lms_url_root,
            'discount_jwt': self.request.GET.get('discount_jwt'),
        })
        return context


class BasketSummaryView(BasketLogicMixin, BasketView):
    @newrelic.agent.function_trace()
    def get_context_data(self, **kwargs):
        context = super(BasketSummaryView, self).get_context_data(**kwargs)
        return self.get_basket_context_data(context)

    @newrelic.agent.function_trace()
    def get(self, request, *args, **kwargs):
        basket = request.basket
        try:
            properties = {
                'cart_id': basket.id,
                'products': [translate_basket_line_for_segment(line) for line in basket.all_lines()],
            }
            track_segment_event(request.site, request.user, 'Cart Viewed', properties)

            properties = {
                'checkout_id': basket.order_number,
                'step': 1
            }
            track_segment_event(request.site, request.user, 'Checkout Step Viewed', properties)
        except Exception:  # pylint: disable=broad-except
            logger.exception('Failed to fire Cart Viewed event for basket [%d]', basket.id)

        if has_enterprise_offer(basket) and basket.total_incl_tax == Decimal(0):
            return redirect('checkout:free-checkout')

        if self._is_single_course_purchase(basket):
            redirect_response = _redirect_to_payment_microfrontend_if_configured(request)
            if redirect_response:
                return redirect_response

        if any(discount.get('offer').name == 'dynamic condition' for discount in basket.offer_applications):
            messages.info(request, 'The new purchaser discount was automatically added.')
        return super(BasketSummaryView, self).get(request, *args, **kwargs)

    def _is_single_course_purchase(self, basket):
        return (
            basket.num_items == 1 and
            basket.lines.count() == 1 and
            basket.lines.first().product.is_seat_product
        )


class PaymentApiLogicMixin(BasketLogicMixin):
    """
    Business logic for the various Payment APIs.
    """

    def _get_order_total(self, context):
        """
        Add the order total to the context in preparation for the get_basket_context_data call.

        Note: We only calculate what we need.  This result is required before calling the shared
        ``get_basket_context_data(context)`` call.

        See https://github.com/django-oscar/django-oscar/blob/1.5.4/src/oscar/apps/basket/views.py#L92-L132
        """
        shipping_charge = Price('USD', Decimal(0))
        context['order_total'] = OrderTotalCalculator().calculate(self.request.basket, shipping_charge)
        return context

    def get_serialized_basket(self, context):
        """
        Serializes the basket.

        Args:
            context (dict): pre-calculated context data
            errors (list): array of error details
        """

        serialized_basket = {
            'basket_id': context['basket_id'],
            'is_free_basket': context['free_basket'],
            'total_excl_discount': context['order_total'].excl_tax + 12,
            'calculated_discount': context['total_benefit'],
            'order_total': context['order_total'].excl_tax,
            'products': [],
            'show_voucher_form': True,
            'payment_providers': [
                {
                    'type': 'cybersource',
                },
                {
                    'type': 'paypal',
                }
            ],
        }

        for line_data in context['lines_data']:
            serialized_basket['products'].append({
                'sku': line_data['sku'],
                'title': line_data['product_title'],
                'image_url': line_data['image_url'],
                'seat_type': line_data['seat_type'],
            })

        voucher = self.request.basket.vouchers.first()
        if voucher:
            serialized_basket['voucher'] = {
                'id': voucher.id,
                'code': voucher.code,
                "benefit": {
                    "type": voucher.benefit.type,
                    "value": voucher.benefit.value,
                },
            }

        return serialized_basket

    def get_payment_api_response(self, errors=None):
        """
        Serializes the payment api response.

        Args:
            errors (list or dict): list of error dicts, or an error dict
        """

        context = {
            'basket_id': self.request.basket.id,
        }
        context = self._get_order_total(context)
        context['line_list'] = self.request.basket.all_lines()
        context = self.get_basket_context_data(context)

        # TODO: ARCH-867: Remove unnecessary processing of anything added to context (e.g. payment_processors) that
        # isn't ultimately passed on to the response.

        response = self.get_serialized_basket(context)
        if errors:
            response['errors'] = errors if isinstance(errors, list) else [errors]
        # TODO: ARCH-983: Check for and also return unexpected flash message errors and warnings

        return response


# TODO: ARCH-967: Remove "pragma: no cover"
class PaymentApiView(PaymentApiLogicMixin, APIView):  # pragma: no cover
    """
    Api for retrieving basket contents and checkout/payment options.

    # TODO: ARCH-867: See ticket for clean-up and refactoring details for this API code.

    GET:
    Retrieves basket contents and checkout/payment options.
    """
    permission_classes = (IsAuthenticated,)

    def get(self, request):  # pylint: disable=unused-argument
        response = self.get_payment_api_response()
        return Response(response)


class VoucherAddLogicMixin(object):
    """
    VoucherAdd logic for adding a voucher.
    """
    def apply_voucher_to_basket(self, voucher):
        """
        Validates and applies voucher on basket.

        Returns:
            message (dict): Dict containing `user_message` and `message_type` (e.g. 'error', 'warning', or 'info')
        """
        self.request.basket.clear_vouchers()
        username = self.request.user and self.request.user.username
        is_valid, message = validate_voucher(voucher, self.request.user, self.request.basket, self.request.site)
        if not is_valid:
            logger.warning('[Code Redemption Failure] The voucher is not valid for this basket. '
                           'User: %s, Basket: %s, Code: %s, Message: %s',
                           username, self.request.basket.id, voucher.code, message)
            message_response = {
                'message_type': 'error',
                'user_message': message,
            }
            self.request.basket.vouchers.remove(voucher)
            return message_response

        valid, message = apply_voucher_on_basket_and_check_discount(voucher, self.request, self.request.basket)

        if not valid:
            logger.warning('[Code Redemption Failure] The voucher could not be applied to this basket. '
                           'User: %s, Basket: %s, Code: %s, Message: %s',
                           username, self.request.basket.id, voucher.code, message)
            message_response = {
                'message_type': 'warning',
                'user_message': message,
            }
            self.request.basket.vouchers.remove(voucher)
        else:
            message_response = {
                'message_type': 'info',
                'user_message': message,
            }
        return message_response

    def check_for_empty_basket_error(self, code):
        """
        Returns a dict with error_code if the basket is empty, or None if no error.
        """
        username = self.request.user and self.request.user.username
        if self.request.basket.is_empty:
            logger.warning(
                '[Code Redemption Failure] User attempted to apply a code to an empty basket. '
                'User: %s, Basket: %s, Code: %s',
                username, self.request.basket.id, code
            )
            return {
                'error_code': 'empty_basket',
            }
        return None

    def check_for_already_applied_voucher_error(self, code):
        """
        Returns a dict with error_code if the voucher was already applied, or None if no error.
        """
        username = self.request.user and self.request.user.username
        if self.request.basket.contains_voucher(code):
            logger.warning(
                '[Code Redemption Failure] User tried to apply a code that is already applied. '
                'User: %s, Basket: %s, Code: %s',
                username, self.request.basket.id, code
            )
            return {
                'error_code': 'already_applied_voucher',
                'user_message': _("You have already added coupon code '{code}' to your basket.").format(code=code)
            }
        return None

    def get_voucher_from_code(self, code):
        """
        Returns tuple (voucher, error_message (dict)).  Only if voucher is None should you expect an error_message.
        """
        try:
            voucher = self.voucher_model._default_manager.get(code=code)  # pylint: disable=protected-access
            return voucher, None
        except self.voucher_model.DoesNotExist:
            return None, {
                'error_code': 'code_does_not_exist',
                'user_message': _("Coupon code '{code}' does not exist.").format(code=code)
            }


class VoucherAddView(VoucherAddLogicMixin, BaseVoucherAddView):  # pylint: disable=function-redefined
    def form_valid(self, form):
        code = form.cleaned_data['code']
        error_message = self.check_for_empty_basket_error(code)
        if error_message:
            return redirect_to_referrer(self.request, 'basket:summary')

        error_message = self.check_for_already_applied_voucher_error(code)
        if error_message:
            messages.error(self.request, error_message['user_message'])
            return redirect_to_referrer(self.request, 'basket:summary')

        voucher, error_message = self.get_voucher_from_code(code)
        if error_message:
            messages.error(self.request, error_message['user_message'])
            return redirect_to_referrer(self.request, 'basket:summary')

        basket_lines = self.request.basket.all_lines()

        # TODO: for multiline baskets, select the StockRecord for the product associated
        # specifically with the code that was submitted.
        stock_record = basket_lines[0].stockrecord

        offer = voucher.best_offer
        product = stock_record.product
        # TODO: ARCH-955: share this with VoucherAddApiView
        email_confirmation_response = render_email_confirmation_if_required(self.request, offer, product)
        if email_confirmation_response:
            return email_confirmation_response

        # TODO: how do we deal with this and the A/B experiment?
        # TODO: ARCH-956: share this with VoucherAddApiView
        if get_enterprise_customer_from_voucher(self.request.site, voucher) is not None:
            # The below lines only apply if the voucher that was entered is attached
            # to an EnterpriseCustomer. If that's the case, then rather than following
            # the standard redemption flow, we kick the user out to the `redeem` flow.
            # This flow will handle any additional information that needs to be gathered
            # due to the fact that the voucher is attached to an Enterprise Customer.
            params = urlencode(
                {
                    'code': code,
                    'sku': stock_record.partner_sku,
                    'failure_url': self.request.build_absolute_uri(
                        '{path}?{params}'.format(
                            path=reverse('basket:summary'),
                            params=urlencode(
                                {
                                    CONSENT_FAILED_PARAM: code
                                }
                            )
                        )
                    ),
                }
            )
            return HttpResponseRedirect(
                '{path}?{params}'.format(
                    path=reverse('coupons:redeem'),
                    params=params
                )
            )

        message = self.apply_voucher_to_basket(voucher)
        self._set_flash_messages(message)
        return redirect_to_referrer(self.request, 'basket:summary')

    def _set_flash_messages(self, message):
        """
        Sets flash messages as needed.

        Argument:
            message (dict): Dict containing `user_message` and `message_type` (e.g. 'error', 'warning', or 'info')
        """
        if message['message_type'] == 'info':
            messages.info(self.request, message['user_message'])
        elif message['message_type'] == 'warning':
            messages.warning(self.request, message['user_message'])
        else:
            messages.error(self.request, message['user_message'])


# TODO: ARCH-960: Remove "pragma: no cover"
class VoucherAddApiView(VoucherAddLogicMixin, PaymentApiLogicMixin, APIView):  # pragma: no cover
    """
    Api for adding voucher to a basket.

    POST:
    """
    permission_classes = (IsAuthenticated,)
    voucher_model = get_model('voucher', 'voucher')

    def post(self, request):  # pylint: disable=unused-argument
        """
        Adds voucher to a basket using the voucher's code.

        Parameters:
        {
            "code": "SUMMER20"
        }

        If successful, adds voucher and returns 200 and the same response as the payment api.
        If unsuccessful, returns 400 with the errors and the same response as the payment api.
        """
        code = request.data.get('code')

        error_message = self.check_for_empty_basket_error(code)
        if error_message:
            return Response(error_message, status=status.HTTP_400_BAD_REQUEST)

        voucher, error_message = self.get_voucher_from_code(code)
        if error_message:
            return Response(error_message, status=status.HTTP_400_BAD_REQUEST)

        # TODO: ARCH-955: implement render_email_confirmation_if_required check
        # TODO: ARCH-956: implement get_enterprise_customer_from_voucher check

        message = self.apply_voucher_to_basket(voucher)
        if message['message_type'] in ('warning', 'error'):
            error_message = {
                'user_message': message['user_message']
            }
            response = self.get_payment_api_response(error_message)
            return Response(response, status=status.HTTP_400_BAD_REQUEST)

        response = self.get_payment_api_response()
        return Response(response)


# TODO: ARCH-960: Remove "pragma: no cover"
class VoucherRemoveApiView(PaymentApiLogicMixin, APIView):  # pragma: no cover
    """
    Api for removing voucher from a basket.

    DELETE /bff/payment/v0/vouchers/{voucherid}
    """
    permission_classes = (IsAuthenticated,)
    voucher_model = get_model('voucher', 'voucher')
    remove_signal = signals.voucher_removal

    def delete(self, request, voucherid):  # pylint: disable=unused-argument
        """
        If successful, removes voucher and returns 200 and the same response as the payment api.
        If unsuccessful, returns 400 with relevant errors and the same response as the payment api.
        """

        # Implementation is a copy of django-oscar's VoucherRemoveView without redirect, and other minor changes.
        # See: https://github.com/django-oscar/django-oscar/blob/3ee66877a2dbd49b2a0838c369205f4ffbc2a391/src/oscar/apps/basket/views.py#L389-L414  pylint: disable=line-too-long

        if not request.basket.id:
            # Hacking attempt - the basket must be saved for it to have
            # a voucher in it.
            # Note: original django-oscar code had no error message.
            error = {
                'error_code': 'invalid_add_voucher_request'
            }
            response = self.get_payment_api_response(error)
            return Response(response, status=status.HTTP_400_BAD_REQUEST)

        try:
            voucher = request.basket.vouchers.get(id=voucherid)
        except ObjectDoesNotExist:
            error = {
                'user_message': _("No voucher found with id '%s'") % voucherid
            }
            response = self.get_payment_api_response(error)
            return Response(response)

        request.basket.vouchers.remove(voucher)
        self.remove_signal.send(sender=self, basket=request.basket, voucher=voucher)

        response = self.get_payment_api_response()
        return Response(response)
