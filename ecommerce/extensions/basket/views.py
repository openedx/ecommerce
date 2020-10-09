# pylint: disable=no-else-return


import logging
import time
import urllib
from collections import OrderedDict
from datetime import datetime
from decimal import Decimal

import dateutil.parser
import newrelic.agent
import waffle
from django.http import HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.html import escape
from django.utils.translation import ugettext as _
from edx_rest_framework_extensions.permissions import LoginRedirectIfUnauthenticated
from opaque_keys.edx.keys import CourseKey
from oscar.apps.basket.signals import voucher_removal
from oscar.apps.basket.views import VoucherAddView as BaseVoucherAddView
from oscar.apps.basket.views import *  # pylint: disable=wildcard-import, unused-wildcard-import
from oscar.core.prices import Price
from requests.exceptions import ConnectionError as ReqConnectionError
from requests.exceptions import Timeout
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from slumber.exceptions import SlumberBaseException

from ecommerce.core.exceptions import SiteConfigurationError
from ecommerce.core.url_utils import absolute_redirect, get_lms_course_about_url, get_lms_url
from ecommerce.courses.utils import get_certificate_type_display_value, get_course_info_from_catalog
from ecommerce.enterprise.utils import (
    CONSENT_FAILED_PARAM,
    construct_enterprise_course_consent_url,
    enterprise_customer_user_needs_consent,
    get_enterprise_customer_from_enterprise_offer,
    get_enterprise_customer_from_voucher,
    has_enterprise_offer
)
from ecommerce.extensions.analytics.utils import (
    prepare_analytics_data,
    track_segment_event,
    translate_basket_line_for_segment
)
from ecommerce.extensions.basket import message_utils
from ecommerce.extensions.basket.constants import EMAIL_OPT_IN_ATTRIBUTE
from ecommerce.extensions.basket.exceptions import BadRequestException, RedirectException, VoucherException
from ecommerce.extensions.basket.utils import (
    add_flex_microform_flag_to_url,
    add_invalid_code_message_to_url,
    add_utm_params_to_url,
    apply_offers_on_basket,
    apply_voucher_on_basket_and_check_discount,
    get_basket_switch_data,
    get_payment_microfrontend_or_basket_url,
    get_payment_microfrontend_url_if_configured,
    prepare_basket,
    validate_voucher
)
from ecommerce.extensions.offer.constants import DYNAMIC_DISCOUNT_FLAG
from ecommerce.extensions.offer.dynamic_conditional_offer import get_percentage_from_request
from ecommerce.extensions.offer.utils import (
    format_benefit_value,
    get_benefit_type,
    get_quantized_benefit_value,
    get_redirect_to_email_confirmation_if_required
)
from ecommerce.extensions.order.exceptions import AlreadyPlacedOrderException
from ecommerce.extensions.partner.shortcuts import get_partner_for_site
from ecommerce.extensions.payment.constants import CLIENT_SIDE_CHECKOUT_FLAG_NAME
from ecommerce.extensions.payment.forms import PaymentForm

Basket = get_model('basket', 'basket')
BasketAttribute = get_model('basket', 'BasketAttribute')
BasketAttributeType = get_model('basket', 'BasketAttributeType')
ConditionalOffer = get_model('offer', 'ConditionalOffer')
Benefit = get_model('offer', 'Benefit')
logger = logging.getLogger(__name__)
Product = get_model('catalogue', 'Product')
StockRecord = get_model('partner', 'StockRecord')
Voucher = get_model('voucher', 'Voucher')
Selector = get_class('partner.strategy', 'Selector')


class BasketLogicMixin:
    """
    Business logic for determining basket contents and checkout/payment options.
    """

    @newrelic.agent.function_trace()
    def process_basket_lines(self, lines):
        """
        Processes the basket lines and extracts information for the view's context.
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
        context_updates = {
            'display_verification_message': False,
            'order_details_msg': None,
            'partner_sku': None,
            'switch_link_text': None,
            'show_voucher_form': bool(lines),
            'is_enrollment_code_purchase': False
        }

        lines_data = []
        for line in lines:
            product = line.product
            if product.is_seat_product or product.is_course_entitlement_product:
                line_data, _ = self._get_course_data(product)

                # TODO this is only used by hosted_checkout_basket template, which may no longer be
                # used. Consider removing both.
                if self._is_id_verification_required(product):
                    context_updates['display_verification_message'] = True
            elif product.is_enrollment_code_product:
                line_data, course = self._get_course_data(product)
                self._set_single_enrollment_code_warning_if_needed(product, course)
                context_updates['is_enrollment_code_purchase'] = True
                context_updates['show_voucher_form'] = False
            else:
                line_data = {
                    'product_title': product.title,
                    'image_url': None,
                    'course_key': None,
                    'product_description': product.description
                }

            context_updates['order_details_msg'] = self._get_order_details_message(product)
            context_updates['switch_link_text'], context_updates['partner_sku'] = get_basket_switch_data(product)

            line_data.update({
                'sku': product.stockrecords.first().partner_sku,
                'benefit_value': self._get_benefit_value(line),
                'enrollment_code': product.is_enrollment_code_product,
                'line': line,
                'seat_type': self._get_certificate_type_display_value(product),
            })
            lines_data.append(line_data)

        return context_updates, lines_data

    def process_totals(self, context):
        """
        Returns a Dictionary of data related to total price and discounts.
        """
        # Total benefit displayed in price summary.
        # Currently only one voucher per basket is supported.
        try:
            applied_voucher = self.request.basket.vouchers.first()
            total_benefit_object = applied_voucher.best_offer.benefit if applied_voucher else None
        # TODO This ValueError handling no longer seems to be required and could probably be removed
        except ValueError:  # pragma: no cover
            total_benefit_object = None

        num_of_items = self.request.basket.num_items

        discount_jwt = None
        discount_percent = None
        if waffle.flag_is_active(self.request, DYNAMIC_DISCOUNT_FLAG):
            applied_offers = self.request.basket.applied_offers().values()
            if len(applied_offers) == 1 and list(applied_offers)[0].condition.name == 'dynamic_discount_condition':
                discount_jwt = self.request.GET.get('discount_jwt')
                discount_percent = get_percentage_from_request()
        return {
            'total_benefit_object': total_benefit_object,
            'total_benefit': format_benefit_value(total_benefit_object) if total_benefit_object else None,
            'free_basket': context['order_total'].incl_tax == 0,
            'line_price': (self.request.basket.total_incl_tax_excl_discounts / num_of_items) if num_of_items > 0 else 0,
            'discount_jwt': discount_jwt,
            'discount_percent': discount_percent,
        }

    def fire_segment_events(self, request, basket):
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

    def verify_enterprise_needs(self, basket):
        failed_enterprise_consent_code = self.request.GET.get(CONSENT_FAILED_PARAM)
        if failed_enterprise_consent_code:
            messages.error(
                self.request,
                _("Could not apply the code '{code}'; it requires data sharing consent.").format(
                    code=failed_enterprise_consent_code
                )
            )

        if has_enterprise_offer(basket) and basket.total_incl_tax == Decimal(0):
            self._redirect_for_enterprise_data_sharing_consent(basket)

            raise RedirectException(
                response=absolute_redirect(self.request, 'checkout:free-checkout'),
            )

    def _redirect_for_enterprise_data_sharing_consent(self, basket):
        """
        Redirect to LMS to get data sharing consent from learner.
        """
        # check if basket contains only a single product of type seat
        if basket.lines.count() == 1 and basket.lines.first().product.is_seat_product:
            enterprise_custmer_uuid = get_enterprise_customer_from_enterprise_offer(basket)
            product = basket.lines.first().product
            course = product.course
            if enterprise_custmer_uuid is not None and enterprise_customer_user_needs_consent(
                    self.request.site,
                    enterprise_custmer_uuid,
                    course.id,
                    self.request.user.username,
            ):
                redirect_url = construct_enterprise_course_consent_url(
                    self.request,
                    product.course.id,
                    enterprise_custmer_uuid
                )
                raise RedirectException(
                    response=HttpResponseRedirect(redirect_url)
                )

    @newrelic.agent.function_trace()
    def _get_course_data(self, product):
        """
        Return course data.

        Args:
            product (Product): A product that has course_key as attribute (seat or bulk enrollment coupon)
        Returns:
            A dictionary containing product title, course key, image URL, description, and start and end dates.
            Also returns course information found from catalog.
        """
        course_data = {
            'product_title': None,
            'course_key': None,
            'image_url': None,
            'product_description': None,
            'course_start': None,
            'course_end': None,
        }
        course = None

        if product.is_seat_product:
            course_data['course_key'] = CourseKey.from_string(product.attr.course_key)

        try:
            course = get_course_info_from_catalog(self.request.site, product)
            try:
                course_data['image_url'] = course['image']['src']
            except (KeyError, TypeError):
                pass

            course_data['product_description'] = course.get('short_description', '')
            course_data['product_title'] = course.get('title', '')

            # The course start/end dates are not currently used
            # in the default basket templates, but we are adding
            # the dates to the template context so that theme
            # template overrides can make use of them.
            course_data['course_start'] = self._deserialize_date(course.get('start'))
            course_data['course_end'] = self._deserialize_date(course.get('end'))
        except (ReqConnectionError, SlumberBaseException, Timeout):
            logger.exception(
                'Failed to retrieve data from Discovery Service for course [%s].',
                course_data['course_key'],
            )

        return course_data, course

    @newrelic.agent.function_trace()
    def _get_order_details_message(self, product):
        if product.is_course_entitlement_product:
            return _(
                'After you complete your order you will be able to select course dates from your dashboard.'
            )
        elif product.is_seat_product:
            try:
                certificate_type = product.attr.certificate_type
            except AttributeError:
                logger.exception(
                    "Failed to get certificate type from seat product: %r, %s, %s",
                    product,
                    product.id,
                    product.is_seat_product
                )
                raise
            if certificate_type == 'verified':
                return _(
                    'After you complete your order you will be automatically enrolled '
                    'in the verified track of the course.'
                )
            elif certificate_type == 'credit':
                return _('After you complete your order you will receive credit for your course.')
            else:
                return _(
                    'After you complete your order you will be automatically enrolled in the course.'
                )
        elif product.is_enrollment_code_product:
            return _(
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
            return None

    @newrelic.agent.function_trace()
    def _set_single_enrollment_code_warning_if_needed(self, product, course):
        assert product.is_enrollment_code_product

        if self.request.basket.num_items == 1:
            course_key = CourseKey.from_string(product.attr.course_key)
            if course and course.get('marketing_url', None):
                course_about_url = course['marketing_url']
            else:
                course_about_url = get_lms_course_about_url(course_key=course_key)

            message_code = 'single-enrollment-code-warning'
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
                extra_tags='safe ' + message_code
            )
            message_utils.add_message_data(message_code, 'course_about_url', course_about_url)

    @newrelic.agent.function_trace()
    def _is_id_verification_required(self, product):
        return (
            getattr(product.attr, 'id_verification_required', False) and
            product.attr.certificate_type != 'credit'
        )

    @newrelic.agent.function_trace()
    def _get_benefit_value(self, line):
        if line.has_discount:
            applied_offer_values = list(self.request.basket.applied_offers().values())
            if applied_offer_values:
                benefit = applied_offer_values[0].benefit
                return format_benefit_value(benefit)
        return None

    @newrelic.agent.function_trace()
    def _get_certificate_type(self, product):
        if product.is_seat_product or product.is_course_entitlement_product:
            return product.attr.certificate_type
        elif product.is_enrollment_code_product:
            return product.attr.seat_type
        return None

    @newrelic.agent.function_trace()
    def _get_certificate_type_display_value(self, product):
        certificate_type = self._get_certificate_type(product)
        if certificate_type:
            return get_certificate_type_display_value(certificate_type)
        return None

    @newrelic.agent.function_trace()
    def _deserialize_date(self, date_string):
        try:
            return dateutil.parser.parse(date_string)
        except (AttributeError, ValueError, TypeError):
            return None


class BasketAddItemsView(BasketLogicMixin, APIView):
    """
    View that adds multiple products to a user's basket.
    An additional coupon code can be supplied so the offer is applied to the basket.
    """
    permission_classes = (LoginRedirectIfUnauthenticated,)

    def get(self, request):
        # Send time when this view is called - https://openedx.atlassian.net/browse/REV-984
        properties = {'emitted_at': time.time()}
        track_segment_event(request.site, request.user, 'Basket Add Items View Called', properties)

        try:
            skus = self._get_skus(request)
            products = self._get_products(request, skus)
            voucher = None
            invalid_code = None
            code = request.GET.get('code', None)
            try:
                voucher = self._get_voucher(request)
            except Voucher.DoesNotExist as e:  # pragma: nocover
                # Display an error message when an invalid code is passed as a parameter
                invalid_code = code

            logger.info('Starting payment flow for user [%s] for products [%s].', request.user.username, skus)

            available_products = self._get_available_products(request, products)

            try:
                basket = prepare_basket(request, available_products, voucher)
            except AlreadyPlacedOrderException:
                return render(request, 'edx/error.html', {'error': _('You have already purchased these products')})

            self._set_email_preference_on_basket(request, basket)

            # Used basket object from request to allow enterprise offers
            # being applied on basket via BasketMiddleware
            self.verify_enterprise_needs(request.basket)
            if code and not request.basket.vouchers.exists():
                if not (len(available_products) == 1 and available_products[0].is_enrollment_code_product):
                    # Display an error message when an invalid code is passed as a parameter
                    invalid_code = code
            return self._redirect_response_to_basket_or_payment(request, invalid_code)

        except BadRequestException as e:
            return HttpResponseBadRequest(str(e))
        except RedirectException as e:
            return e.response

    def _get_skus(self, request):
        skus = [escape(sku) for sku in request.GET.getlist('sku')]
        if not skus:
            raise BadRequestException(_('No SKUs provided.'))
        return skus

    def _get_products(self, request, skus):
        partner = get_partner_for_site(request)
        products = Product.objects.filter(stockrecords__partner=partner, stockrecords__partner_sku__in=skus)
        if not products:
            raise BadRequestException(_('Products with SKU(s) [{skus}] do not exist.').format(skus=', '.join(skus)))
        return products

    def _get_voucher(self, request):
        code = request.GET.get('code', None)
        return Voucher.objects.get(code=code) if code else None

    def _get_available_products(self, request, products):
        unavailable_product_ids = []
        for product in products:
            purchase_info = request.strategy.fetch_for_product(product)
            if not purchase_info.availability.is_available_to_buy:
                logger.warning('Product [%s] is not available to buy.', product.title)
                unavailable_product_ids.append(product.id)

        available_products = products.exclude(id__in=unavailable_product_ids)
        if not available_products:
            raise BadRequestException(_('No product is available to buy.'))
        return available_products

    def _set_email_preference_on_basket(self, request, basket):
        """
        Associate the user's email opt in preferences with the basket in
        order to opt them in later as part of fulfillment
        """
        BasketAttribute.objects.update_or_create(
            basket=basket,
            attribute_type=BasketAttributeType.objects.get(name=EMAIL_OPT_IN_ATTRIBUTE),
            defaults={'value_text': request.GET.get('email_opt_in') == 'true'},
        )

    def _redirect_response_to_basket_or_payment(self, request, invalid_code=None):
        redirect_url = get_payment_microfrontend_or_basket_url(request)
        redirect_url = add_utm_params_to_url(redirect_url, list(self.request.GET.items()))
        redirect_url = add_invalid_code_message_to_url(redirect_url, invalid_code)
        # TODO: Remove as part of PCI-81
        redirect_url = add_flex_microform_flag_to_url(redirect_url, request)

        return HttpResponseRedirect(redirect_url, status=303)


class BasketSummaryView(BasketLogicMixin, BasketView):
    @newrelic.agent.function_trace()
    def get_context_data(self, **kwargs):
        context = super(BasketSummaryView, self).get_context_data(**kwargs)
        return self._add_to_context_data(context)

    @newrelic.agent.function_trace()
    def get(self, request, *args, **kwargs):
        basket = request.basket

        try:
            self.fire_segment_events(request, basket)
            self.verify_enterprise_needs(basket)
            self._redirect_to_payment_microfrontend_if_configured(request)
        except RedirectException as e:
            return e.response

        return super(BasketSummaryView, self).get(request, *args, **kwargs)

    def _redirect_to_payment_microfrontend_if_configured(self, request):
        microfrontend_url = get_payment_microfrontend_url_if_configured(request)
        if microfrontend_url:
            # For now, the enterprise consent form validation is communicated via
            # a URL parameter, which must be forwarded via this redirect.
            consent_failed_param_to_forward = request.GET.get(CONSENT_FAILED_PARAM)
            if consent_failed_param_to_forward:
                microfrontend_url = '{}?{}={}'.format(
                    microfrontend_url,
                    CONSENT_FAILED_PARAM,
                    consent_failed_param_to_forward,
                )
            redirect_response = HttpResponseRedirect(microfrontend_url)
            raise RedirectException(response=redirect_response)

    @newrelic.agent.function_trace()
    def _add_to_context_data(self, context):
        formset = context.get('formset', [])
        lines = context.get('line_list', [])
        site_configuration = self.request.site.siteconfiguration

        context_updates, lines_data = self.process_basket_lines(lines)
        context.update(context_updates)
        context.update(self.process_totals(context))

        context.update({
            'analytics_data': prepare_analytics_data(
                self.request.user,
                site_configuration.segment_key,
            ),
            'enable_client_side_checkout': False,
            'sdn_check': site_configuration.enable_sdn_check
        })

        payment_processors = site_configuration.get_payment_processors()
        if (
                site_configuration.client_side_payment_processor and
                waffle.flag_is_active(self.request, CLIENT_SIDE_CHECKOUT_FLAG_NAME)
        ):
            payment_processors_data = self._get_payment_processors_data(payment_processors)
            context.update(payment_processors_data)

        context.update({
            'formset_lines_data': list(zip(formset, lines_data)),
            'homepage_url': get_lms_url(''),
            'min_seat_quantity': 1,
            'max_seat_quantity': 100,
            'payment_processors': payment_processors,
            'lms_url_root': site_configuration.lms_url_root,
        })
        return context

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


class CaptureContextApiLogicMixin:  # pragma: no cover
    """
    Business logic for the capture context API.
    """
    def _add_capture_context(self, response):
        response['flex_microform_enabled'] = waffle.flag_is_active(
            self.request,
            'payment.cybersource.flex_microform_enabled'
        )
        if not response['flex_microform_enabled']:
            return
        payment_processor_class = self.request.site.siteconfiguration.get_client_side_payment_processor_class()
        if not payment_processor_class:
            return
        payment_processor = payment_processor_class(self.request.site)
        if not hasattr(payment_processor, 'get_capture_context'):
            return

        try:
            response['capture_context'] = payment_processor.get_capture_context(self.request.session)
        except:  # pylint: disable=bare-except
            logger.exception("Error generating capture_context")
            return


class PaymentApiLogicMixin(BasketLogicMixin):
    """
    Business logic for the various Payment APIs.
    """
    def get_payment_api_response(self, status=None):
        """
        Serializes the payment api response.
        """
        context, lines_data = self.process_basket_lines(self.request.basket.all_lines())

        context['order_total'] = self._get_order_total()
        context.update(self.process_totals(context))

        data = self._serialize_context(context, lines_data)
        self._add_messages(data)
        response_status = status if status else self._get_response_status(data)
        return Response(data, status=response_status)

    def reload_basket(self):
        """
        After basket updates, we need to reload the basket to ensure everything is up to date.
        """
        self.request.basket = get_model('basket', 'Basket').objects.get(id=self.request.basket.id)
        self.request.basket.strategy = self.request.strategy
        apply_offers_on_basket(self.request, self.request.basket)

    def _get_order_total(self):
        """
        Return the order_total in preparation for call to process_totals.
        See https://github.com/django-oscar/django-oscar/blob/1.5.4/src/oscar/apps/basket/views.py#L92-L132
        for reference in how this is calculated by django-oscar.
        """
        shipping_charge = Price('USD', excl_tax=Decimal(0), tax=Decimal(0))
        return OrderTotalCalculator().calculate(self.request.basket, shipping_charge)

    def _serialize_context(self, context, lines_data):
        """
        Serializes the data in the given context.

        Args:
            context (dict): pre-calculated context data
        """
        response = {
            'basket_id': self.request.basket.id,
            'is_free_basket': context['free_basket'],
            'currency': self.request.basket.currency,
        }

        self._add_products(response, lines_data)
        self._add_total_summary(response, context)
        self._add_offers(response)
        self._add_coupons(response, context)
        return response

    def _add_products(self, response, lines_data):
        response['products'] = [
            {
                'course_key': getattr(line_data['line'].product.attr, 'course_key', None),
                'sku': line_data['sku'],
                'title': line_data['product_title'],
                'product_type': line_data['line'].product.get_product_class().name,
                'image_url': line_data['image_url'],
                'certificate_type': self._get_certificate_type(line_data['line'].product),
            }
            for line_data in lines_data
        ]

    def _add_total_summary(self, response, context):
        if context['is_enrollment_code_purchase']:
            response['summary_price'] = context['line_price']
            response['summary_quantity'] = self.request.basket.num_items
            response['summary_subtotal'] = context['order_total'].incl_tax
        else:
            response['summary_price'] = self.request.basket.total_incl_tax_excl_discounts

        response['summary_discounts'] = self.request.basket.total_discount
        response['order_total'] = context['order_total'].incl_tax

    def _add_offers(self, response):
        response['offers'] = [
            {
                'provider': offer.condition.enterprise_customer_name,
                'name': offer.name,
                'benefit_type': get_benefit_type(offer.benefit) if offer.benefit else None,
                'benefit_value': get_quantized_benefit_value(offer.benefit) if offer.benefit else None,
            }
            for offer in self.request.basket.applied_offers().values()
            if (offer.condition.enterprise_customer_name or
                (offer.condition.name and offer.offer_type == ConditionalOffer.SITE))
        ]

    def _add_coupons(self, response, context):
        response['show_coupon_form'] = context['show_voucher_form']
        benefit = context['total_benefit_object']
        response['coupons'] = [
            {
                'id': voucher.id,
                'code': voucher.code,
                'benefit_type': get_benefit_type(benefit) if benefit else None,
                'benefit_value': get_quantized_benefit_value(benefit) if benefit else None,
            }
            for voucher in self.request.basket.vouchers.all()
            if response['show_coupon_form'] and self.request.basket.contains_a_voucher
        ]

    def _add_messages(self, response):
        response['messages'] = message_utils.serialize(self.request)

    def _get_response_status(self, response):
        return message_utils.get_response_status(response['messages'])


class CaptureContextApiView(CaptureContextApiLogicMixin, APIView):  # pragma: no cover
    """
    Api for retrieving capture context / public key for the Cybersource flex-form.

    GET:
        Retrieves a capture context / public key for the Cybersource flex-form.
    """
    permission_classes = (IsAuthenticated,)

    def get(self, request):  # pylint: disable=unused-argument
        try:
            return self.get_capture_context_api_response()
        except RedirectException as e:
            return Response({'redirect': e.response.url})

    def get_capture_context_api_response(self, status=None):
        """
        Serializes the capture context api response.
        """
        data = {}
        self._add_capture_context(data)
        return Response(data, status=status)


class PaymentApiView(PaymentApiLogicMixin, APIView):
    """
    Api for retrieving basket contents and checkout/payment options.

    GET:
        Retrieves basket contents and checkout/payment options.
    """
    permission_classes = (IsAuthenticated,)

    def get(self, request):  # pylint: disable=unused-argument
        basket = request.basket

        try:
            self.fire_segment_events(request, basket)
            self.verify_enterprise_needs(basket)
            return self.get_payment_api_response()
        except RedirectException as e:
            return Response({'redirect': e.response.url})


class QuantityAPIView(APIView, View, PaymentApiLogicMixin):
    """
    API to handle bulk code purchasing by setting the quantity.

    Note: DRF APIView wrapper allows clients to use JWT authentication

    """
    permission_classes = (IsAuthenticated,)
    http_method_names = ['post', 'options']

    def post(self, request):
        """
        Updates quantity for a basket.

        Note: This only works for single-product baskets.

        """
        if request.basket.is_empty:
            return self.get_payment_api_response(status=400)

        basket_line = self._get_first_basket_line()
        if not basket_line.product.is_enrollment_code_product:
            return self.get_payment_api_response(status=400)

        # NOTE: Ideally, we'd inherit FormView; but that doesn't work with APIView
        form = self._get_basket_line_form(basket_line)
        if form.is_valid():
            form.save()
            return self._form_valid()

        return self._form_invalid(form)

    def _get_first_basket_line(self):
        """ Get first line from basket. """
        basket_lines = self.request.basket.all_lines()
        assert basket_lines
        return basket_lines[0]

    def _get_basket_line_form(self, basket_line):
        """ Retrieves form for the first line. """
        form_kwargs = {
            'data': self.request.data,
            'strategy': self.request.strategy,
            'instance': basket_line
        }
        return BasketLineForm(**form_kwargs)

    def _form_valid(self):
        """
        The following code was adapted from django-oscar's BasketView.formset_valid.

        Changes from BasketView.formset_valid:
        - Does not duplicate `save_for_later` related functionality.
        - Similar to is_ajax() branch of BasketView.formset_valid, but this code actually works.
        - Offers messaging was dropped.  These messages contain HTML, but no message code (see BasketMessageGenerator).

        """
        self.reload_basket()
        # Note: the original message included HTML, so the client should build its own success message
        messages.info(self.request, _('quantity successfully updated'), extra_tags='quantity-update-success-message')

        return self.get_payment_api_response()

    def _get_clean_error_messages(self, errors):
        msgs = []
        for error in errors:
            msgs.append(error.as_text())
        # The removal of '*' may not be needed. It was copied from a different view (BasketAddView) in django-oscar.
        # See https://github.com/django-oscar/django-oscar/blob/3ee66877a2dbd49b2a0838c369205f4ffbc2a391/src/oscar/apps/basket/views.py#L261-L265  pylint: disable=line-too-long
        clean_msgs = [m.replace('* ', '') for m in msgs if m.startswith('* ')]
        return ",".join(clean_msgs)

    def _form_invalid(self, form):
        """
        The following code was adapted from django-oscar's BasketView.formset_invalid.
        """
        messages.warning(
            self.request,
            _("Your basket couldn't be updated. Please correct any validation errors below.")
        )
        if form.errors:
            messages.warning(self.request, self._get_clean_error_messages(form.errors.values()))
        else:  # pragma: no cover
            pass
        return self.get_payment_api_response(status=400)


class VoucherAddLogicMixin:
    """
    VoucherAdd logic for adding a voucher.
    """
    def verify_and_apply_voucher(self, code):
        """
        Verifies the voucher for the given code before applying it to the basket.

        Raises:
            VoucherException in case of an error.
            RedirectException if a redirect is needed.
        """
        self._verify_basket_not_empty(code)
        self._verify_voucher_not_already_applied(code)

        stock_record = self._get_stock_record()
        voucher = self._get_voucher(code)

        self._verify_email_confirmation(voucher, stock_record.product)
        self._verify_enterprise_needs(voucher, code, stock_record)

        self.request.basket.clear_vouchers()
        self._validate_voucher(voucher)
        self._apply_voucher(voucher)

    def _verify_basket_not_empty(self, code):
        username = self.request.user and self.request.user.username
        if self.request.basket.is_empty:
            logger.warning(
                '[Code Redemption Failure] User attempted to apply a code to an empty basket. '
                'User: %s, Basket: %s, Code: %s',
                username, self.request.basket.id, code
            )
            raise VoucherException()

    def _verify_voucher_not_already_applied(self, code):
        username = self.request.user and self.request.user.username
        if self.request.basket.contains_voucher(code):
            logger.warning(
                '[Code Redemption Failure] User tried to apply a code that is already applied. '
                'User: %s, Basket: %s, Code: %s',
                username, self.request.basket.id, code
            )
            messages.error(
                self.request,
                _("You have already added coupon code '{code}' to your basket.").format(code=code),
            )
            raise VoucherException()

    def _verify_email_confirmation(self, voucher, product):
        offer = voucher.best_offer
        redirect_response = get_redirect_to_email_confirmation_if_required(self.request, offer, product)
        if redirect_response:
            raise RedirectException(response=redirect_response)

    def _verify_enterprise_needs(self, voucher, code, stock_record):
        if get_enterprise_customer_from_voucher(self.request.site, voucher) is not None:
            # The below lines only apply if the voucher that was entered is attached
            # to an EnterpriseCustomer. If that's the case, then rather than following
            # the standard redemption flow, we kick the user out to the `redeem` flow.
            # This flow will handle any additional information that needs to be gathered
            # due to the fact that the voucher is attached to an Enterprise Customer.
            params = urllib.parse.urlencode(
                OrderedDict([
                    ('code', code),
                    ('sku', stock_record.partner_sku),
                    ('failure_url', self.request.build_absolute_uri(
                        '{path}?{params}'.format(
                            path=reverse('basket:summary'),
                            params=urllib.parse.urlencode(
                                {
                                    CONSENT_FAILED_PARAM: code
                                }
                            )
                        )
                    ))
                ])
            )
            redirect_response = HttpResponseRedirect(
                self.request.build_absolute_uri(
                    '{path}?{params}'.format(
                        path=reverse('coupons:redeem'),
                        params=params
                    )
                )
            )
            raise RedirectException(response=redirect_response)

    def _validate_voucher(self, voucher):
        username = self.request.user and self.request.user.username
        is_valid, message = validate_voucher(voucher, self.request.user, self.request.basket, self.request.site)
        if not is_valid:
            logger.warning('[Code Redemption Failure] The voucher is not valid for this basket. '
                           'User: %s, Basket: %s, Code: %s, Message: %s',
                           username, self.request.basket.id, voucher.code, message)
            messages.error(self.request, message)
            self.request.basket.vouchers.remove(voucher)
            raise VoucherException()

    def _apply_voucher(self, voucher):
        username = self.request.user and self.request.user.username
        valid, message = apply_voucher_on_basket_and_check_discount(voucher, self.request, self.request.basket)
        if not valid:
            logger.warning('[Code Redemption Failure] The voucher could not be applied to this basket. '
                           'User: %s, Basket: %s, Code: %s, Message: %s',
                           username, self.request.basket.id, voucher.code, message)
            messages.warning(self.request, message)
            self.request.basket.vouchers.remove(voucher)
        else:
            messages.info(self.request, message)

    def _get_stock_record(self):
        # TODO: for multiline baskets, select the StockRecord for the product associated
        # specifically with the code that was submitted.
        basket_lines = self.request.basket.all_lines()
        return basket_lines[0].stockrecord

    def _get_voucher(self, code):
        try:
            return self.voucher_model._default_manager.get(code=code)  # pylint: disable=protected-access
        except self.voucher_model.DoesNotExist:
            messages.error(self.request, _("Coupon code '{code}' does not exist.").format(code=code))
            raise VoucherException()


class VoucherAddView(VoucherAddLogicMixin, BaseVoucherAddView):  # pylint: disable=function-redefined
    """
    Deprecated: Adds a voucher to the basket.

    Ensure any changes made here are also made to VoucherAddApiView.
    """
    def form_valid(self, form):
        code = form.cleaned_data['code']

        try:
            self.verify_and_apply_voucher(code)
        except RedirectException as e:
            return e.response
        except VoucherException:
            # errors are passed via messages object
            pass

        return redirect_to_referrer(self.request, 'basket:summary')


class VoucherAddApiView(VoucherAddLogicMixin, PaymentApiLogicMixin, APIView):
    """
    Api for adding voucher to a basket.

    POST:
    """
    permission_classes = (IsAuthenticated,)
    voucher_model = get_model('voucher', 'voucher')

    def post(self, request):
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
        code = code.strip()

        try:
            self.verify_and_apply_voucher(code)
            status = 200
        except RedirectException as e:
            return Response({'redirect': e.response.url})
        except VoucherException:
            # errors are passed via messages object and handled during serialization
            status = 400

        return self.get_payment_api_response(status=status)


class VoucherRemoveApiView(PaymentApiLogicMixin, APIView):
    """
    Api for removing voucher from a basket.

    DELETE /bff/payment/v0/vouchers/{voucherid}
    """
    permission_classes = (IsAuthenticated,)
    voucher_model = get_model('voucher', 'voucher')
    remove_signal = voucher_removal

    def delete(self, request, voucherid):  # pylint: disable=unused-argument
        """
        If successful, removes voucher and returns 200 and the same response as the payment api.
        If unsuccessful, returns 400 with relevant errors and the same response as the payment api.
        """

        # Implementation is a copy of django-oscar's VoucherRemoveView without redirect, and other minor changes.
        # See: https://github.com/django-oscar/django-oscar/blob/3ee66877a2dbd49b2a0838c369205f4ffbc2a391/src/oscar/apps/basket/views.py#L389-L414  pylint: disable=line-too-long

        # Note: This comment is from original django-oscar code.
        # Hacking attempt - the basket must be saved for it to have a voucher in it.
        if self.request.basket.id:
            try:
                voucher = request.basket.vouchers.get(id=voucherid)
            except ObjectDoesNotExist:
                messages.error(self.request, _("No coupon found with id '%s'") % voucherid)
            else:
                self.request.basket.vouchers.remove(voucher)
                self.remove_signal.send(sender=self, basket=self.request.basket, voucher=voucher)
                messages.info(request, _("Coupon code '%s' was removed from your basket.") % voucher.code)

        self.reload_basket()
        return self.get_payment_api_response()
