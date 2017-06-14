from __future__ import unicode_literals

import logging
from collections import OrderedDict
from datetime import datetime
from urllib import urlencode

import dateutil.parser
import waffle
from django.contrib.sites.shortcuts import get_current_site
from django.http import HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import render
from django.utils.translation import ugettext as _
from opaque_keys.edx.keys import CourseKey
from oscar.apps.basket.views import VoucherAddView as BaseVoucherAddView
from oscar.apps.basket.views import VoucherRemoveView as BaseVoucherRemoveView
from oscar.apps.basket.views import *  # pylint: disable=wildcard-import, unused-wildcard-import
from oscar.core.decorators import deprecated
from requests.exceptions import ConnectionError, Timeout
from slumber.exceptions import SlumberBaseException

from ecommerce.core.exceptions import SiteConfigurationError
from ecommerce.core.url_utils import get_lms_url
from ecommerce.courses.utils import get_certificate_type_display_value, get_course_info_from_catalog
from ecommerce.enterprise.entitlements import get_entitlement_voucher
from ecommerce.enterprise.utils import CONSENT_FAILED_PARAM, get_enterprise_customer_from_voucher
from ecommerce.extensions.analytics.utils import prepare_analytics_data
from ecommerce.extensions.basket.utils import get_basket_switch_data, prepare_basket
from ecommerce.extensions.offer.utils import format_benefit_value, render_email_confirmation_if_required
from ecommerce.extensions.order.exceptions import AlreadyPlacedOrderException
from ecommerce.extensions.partner.shortcuts import get_partner_for_site
from ecommerce.extensions.payment.constants import CLIENT_SIDE_CHECKOUT_FLAG_NAME
from ecommerce.extensions.payment.forms import PaymentForm

Benefit = get_model('offer', 'Benefit')
logger = logging.getLogger(__name__)
Product = get_model('catalogue', 'Product')
StockRecord = get_model('partner', 'StockRecord')
Voucher = get_model('voucher', 'Voucher')


@deprecated
class BasketSingleItemView(View):
    """
    View that adds a single product to a user's basket.
    An additional coupon code can be supplied so the offer is applied to the basket.
    """

    def get(self, request):
        partner = get_partner_for_site(request)

        sku = request.GET.get('sku', None)
        code = request.GET.get('code', None)
        consent_failed = request.GET.get(CONSENT_FAILED_PARAM, False)

        if not sku:
            return HttpResponseBadRequest(_('No SKU provided.'))

        voucher = Voucher.objects.get(code=code) if code else None

        try:
            product = StockRecord.objects.get(partner=partner, partner_sku=sku).product
        except StockRecord.DoesNotExist:
            return HttpResponseBadRequest(_('SKU [{sku}] does not exist.').format(sku=sku))

        if not consent_failed and voucher is None:
            # Find and apply the enterprise entitlement on the learner basket. First, check two things:
            # 1. We don't already have an existing voucher parsed from a URL parameter
            # 2. The `consent_failed` URL parameter is falsey, or missing, meaning that we haven't already
            # attempted to apply an Enterprise voucher at least once, but the user rejected consent. Failing
            # to make that check would result in the user being repeatedly prompted to grant consent for the
            # same coupon they already declined consent on.
            voucher = get_entitlement_voucher(request, product)
            if voucher is not None:
                params = urlencode(
                    OrderedDict([
                        ('code', voucher.code),
                        ('sku', sku),
                        # This view does not handle getting data sharing consent. However, the coupon redemption
                        # view does. By adding the `failure_url` parameter, we're informing that view that, in the
                        # event required consent for a coupon can't be collected, the user ought to be directed
                        # back to this single-item basket view, with the `consent_failed` parameter applied so that
                        # we know not to try to apply the enterprise coupon again.
                        (
                            'failure_url', request.build_absolute_uri(
                                '{path}?{params}'.format(
                                    path=reverse('basket:single-item'),
                                    params=urlencode(
                                        OrderedDict([
                                            (CONSENT_FAILED_PARAM, True),
                                            ('sku', sku),
                                        ])
                                    )
                                )
                            ),
                        ),
                    ])
                )
                return HttpResponseRedirect(
                    '{path}?{params}'.format(
                        path=reverse('coupons:redeem'),
                        params=params
                    )
                )

        # If the product isn't available then there's no reason to continue with the basket addition
        purchase_info = request.strategy.fetch_for_product(product)
        if not purchase_info.availability.is_available_to_buy:
            msg = _('Product [{product}] not available to buy.').format(product=product.title)
            return HttpResponseBadRequest(msg)

        # At this point we're either adding an Enrollment Code product to the basket,
        # or the user is adding a Seat product for which they are not already enrolled
        try:
            prepare_basket(request, [product], voucher)
        except AlreadyPlacedOrderException:
            msg = _('You have already purchased {course} seat.').format(course=product.course.name)
            return render(request, 'edx/error.html', {'error': msg})
        return HttpResponseRedirect(reverse('basket:summary'), status=303)


class BasketMultipleItemsView(View):
    """
    View that adds multiple products to a user's basket.
    An additional coupon code can be supplied so the offer is applied to the basket.
    """

    def get(self, request):
        partner = get_partner_for_site(request)

        skus = request.GET.getlist('sku')
        code = request.GET.get('code', None)

        if not skus:
            return HttpResponseBadRequest(_('No SKUs provided.'))

        products = Product.objects.filter(stockrecords__partner=partner, stockrecords__partner_sku__in=skus)
        if not products:
            return HttpResponseBadRequest(_('Products with SKU(s) [{skus}] do not exist.').format(skus=', '.join(skus)))

        voucher = Voucher.objects.get(code=code) if code else None
        try:
            prepare_basket(request, products, voucher)
        except AlreadyPlacedOrderException:
            return render(request, 'edx/error.html', {'error': _('You have already purchased these products')})
        messages.add_message(request, messages.INFO, 'Already purchased products will not be added to basket.')
        return HttpResponseRedirect(reverse('basket:summary'), status=303)


class BasketSummaryView(BasketView):
    """
    Display basket contents and checkout/payment options.
    """

    def _determine_seat_type(self, product):
        """
        Return the seat type based on the product class
        """
        seat_type = None
        if product.is_seat_product:
            seat_type = get_certificate_type_display_value(product.attr.certificate_type)
        elif product.is_enrollment_code_product:
            seat_type = get_certificate_type_display_value(product.attr.seat_type)
        return seat_type

    def _deserialize_date(self, date_string):
        date = None
        try:
            date = dateutil.parser.parse(date_string)
        except (AttributeError, ValueError):
            pass
        return date

    def _get_course_data(self, product):
        """
        Return course data.

        Args:
            product (Product): A product that has course_key as attribute (seat or bulk enrollment coupon)
        Returns:
            Dictionary containing course name, course key, course image URL and description.
        """
        course_key = CourseKey.from_string(product.attr.course_key)
        course_name = None
        image_url = None
        short_description = None
        course_start = None
        course_end = None

        try:
            course = get_course_info_from_catalog(self.request.site, course_key)
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
            logger.exception('Failed to retrieve data from Catalog Service for course [%s].', course_key)

        return {
            'product_title': course_name,
            'course_key': course_key,
            'image_url': image_url,
            'product_description': short_description,
            'course_start': course_start,
            'course_end': course_end,
        }

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
        switch_link_text = partner_sku = order_details_msg = None

        for line in lines:
            if line.product.is_seat_product:
                line_data = self._get_course_data(line.product)
                certificate_type = line.product.attr.certificate_type

                if getattr(line.product.attr, 'id_verification_required', False) and certificate_type != 'credit':
                    display_verification_message = True

                if certificate_type == 'verified':
                    order_details_msg = _(
                        'You will be automatically enrolled in the verified track'
                        ' of the course upon completing your order.'
                    )
                elif certificate_type == 'credit':
                    order_details_msg = _('You will receive your credit upon completing your order.')
                else:
                    order_details_msg = _(
                        'You will be automatically enrolled in the course upon completing your order.'
                    )
            elif line.product.is_enrollment_code_product:
                line_data = self._get_course_data(line.product)
                show_voucher_form = False
                order_details_msg = _(
                    'You will receive an email at {user_email} with your enrollment code(s).'
                ).format(user_email=self.request.user.email)
            else:
                line_data = {
                    'product_title': line.product.title,
                    'image_url': None,
                    'product_description': line.product.description
                }

            # TODO: handle these links for multi-line baskets.
            if self.request.site.siteconfiguration.enable_enrollment_codes:
                # Get variables for the switch link that toggles from enrollment codes and seat.
                switch_link_text, partner_sku = get_basket_switch_data(line.product)

            if line.has_discount:
                benefit = self.request.basket.applied_offers().values()[0].benefit
                benefit_value = format_benefit_value(benefit)
            else:
                benefit_value = None

            line_data.update({
                'benefit_value': benefit_value,
                'enrollment_code': line.product.is_enrollment_code_product,
                'line': line,
                'seat_type': self._determine_seat_type(line.product),
            })
            lines_data.append(line_data)

        context_updates = {
            'display_verification_message': display_verification_message,
            'order_details_msg': order_details_msg,
            'partner_sku': partner_sku,
            'show_voucher_form': show_voucher_form,
            'switch_link_text': switch_link_text
        }

        return context_updates, lines_data

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
                'months': range(1, 13),
                'payment_form': PaymentForm(
                    user=self.request.user, initial={'basket': self.request.basket}, label_suffix=''
                ),
                'paypal_enabled': 'paypal' in (p.NAME for p in payment_processors),
                # Assumption is that the credit card duration is 15 years
                'years': range(current_year, current_year + 16),
            }
        else:
            msg = 'Unable to load client-side payment processor [{processor}] for ' \
                  'site configuration [{sc}]'.format(processor=site_configuration.client_side_payment_processor,
                                                     sc=site_configuration.id)
            raise SiteConfigurationError(msg)

    def get_context_data(self, **kwargs):
        context = super(BasketSummaryView, self).get_context_data(**kwargs)
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
                format_benefit_value(applied_voucher.offers.first().benefit)
                if applied_voucher else None
            )
        except ValueError:
            total_benefit = None

        context.update({
            'formset_lines_data': zip(formset, lines_data),
            'free_basket': context['order_total'].incl_tax == 0,
            'homepage_url': get_lms_url(''),
            'min_seat_quantity': 1,
            'payment_processors': payment_processors,
            'total_benefit': total_benefit
        })
        return context


class VoucherAddView(BaseVoucherAddView):  # pylint: disable=function-redefined
    def apply_voucher_to_basket(self, voucher):
        code = voucher.code
        if voucher.is_expired():
            messages.error(
                self.request,
                _("Coupon code '{code}' has expired.").format(code=code)
            )
            return

        if not voucher.is_active():
            messages.error(
                self.request,
                _("Coupon code '{code}' is not active.").format(code=code))
            return

        is_available, message = voucher.is_available_to_user(self.request.user)

        if not is_available:
            if voucher.usage == Voucher.SINGLE_USE:
                message = _("Coupon code '{code}' has already been redeemed.").format(code=code)
            messages.error(self.request, message)

            return

        # Reset any site offers that are applied so that only one offer is active.
        self.request.basket.reset_offer_applications()
        self.request.basket.vouchers.add(voucher)

        # Raise signal
        self.add_signal.send(sender=self, basket=self.request.basket, voucher=voucher)

        # Recalculate discounts to see if the voucher gives any
        Applicator().apply(self.request.basket, self.request.user,
                           self.request)
        discounts_after = self.request.basket.offer_applications

        # Look for discounts from this new voucher
        found_discount = False
        for discount in discounts_after:
            if discount['voucher'] and discount['voucher'] == voucher:
                found_discount = True
                break
        if not found_discount:
            messages.warning(
                self.request,
                _('Your basket does not qualify for a coupon code discount.'))
            self.request.basket.vouchers.remove(voucher)
        else:
            messages.info(
                self.request,
                _("Coupon code '{code}' added to basket.").format(code=code)
            )

    def form_valid(self, form):
        code = form.cleaned_data['code']
        if not self.request.basket.id:
            return redirect_to_referrer(self.request, 'basket:summary')
        if self.request.basket.contains_voucher(code):
            messages.error(
                self.request,
                _("You have already added coupon code '{code}' to your basket.").format(code=code)
            )
        else:
            try:
                voucher = self.voucher_model._default_manager.get(code=code)  # pylint: disable=protected-access
            except self.voucher_model.DoesNotExist:
                messages.error(
                    self.request,
                    _("Coupon code '{code}' does not exist.").format(code=code)
                )
            else:
                basket_lines = self.request.basket.all_lines()

                # TODO: for multiline baskets, select the StockRecord for the product associated
                # specifically with the code that was submitted.
                stock_record = basket_lines[0].stockrecord

                offer = voucher.offers.first()
                product = stock_record.product
                email_confirmation_response = render_email_confirmation_if_required(self.request, offer, product)
                if email_confirmation_response:
                    return email_confirmation_response

                if get_enterprise_customer_from_voucher(
                        get_current_site(self.request),
                        voucher,
                ) is not None:
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
                self.apply_voucher_to_basket(voucher)
        return redirect_to_referrer(self.request, 'basket:summary')


class VoucherRemoveView(BaseVoucherRemoveView):  # pylint: disable=function-redefined
    def post(self, request, *args, **kwargs):
        # TODO Remove this once https://github.com/django-oscar/django-oscar/pull/2241 is merged.
        # This prevents an issue that arises when the user applies a voucher, opens the basket page in
        # another window/tab, and attempts to remove the voucher on both screens. Under this scenario the
        # second attempt to remove the voucher will raise an error.
        kwargs['pk'] = int(kwargs['pk'])
        return super(VoucherRemoveView, self).post(request, *args, **kwargs)
