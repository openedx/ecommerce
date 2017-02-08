from __future__ import unicode_literals

from datetime import datetime
import logging

import dateutil.parser
import waffle
from django.http import HttpResponseBadRequest, HttpResponseRedirect
from django.utils.translation import ugettext_lazy as _
from opaque_keys.edx.keys import CourseKey
from oscar.apps.basket.views import *  # pylint: disable=wildcard-import, unused-wildcard-import
from oscar.core.utils import redirect_to_referrer
from requests.exceptions import ConnectionError, Timeout
from slumber.exceptions import SlumberBaseException

from ecommerce.core.constants import ENROLLMENT_CODE_PRODUCT_CLASS_NAME, SEAT_PRODUCT_CLASS_NAME
from ecommerce.core.exceptions import SiteConfigurationError
from ecommerce.core.url_utils import get_lms_url
from ecommerce.courses.utils import get_certificate_type_display_value, get_course_info_from_catalog, mode_for_seat
from ecommerce.enterprise.entitlements import get_entitlement_voucher
from ecommerce.extensions.analytics.utils import prepare_analytics_data
from ecommerce.extensions.basket.utils import get_basket_switch_data, prepare_basket
from ecommerce.extensions.offer.utils import format_benefit_value
from ecommerce.extensions.partner.shortcuts import get_partner_for_site
from ecommerce.extensions.payment.constants import CLIENT_SIDE_CHECKOUT_FLAG_NAME
from ecommerce.extensions.payment.forms import PaymentForm


Benefit = get_model('offer', 'Benefit')
logger = logging.getLogger(__name__)
StockRecord = get_model('partner', 'StockRecord')
Voucher = get_model('voucher', 'Voucher')


class BasketSingleItemView(View):
    """
    View that adds a single product to a user's basket.
    An additional coupon code can be supplied so the offer is applied to the basket.
    """

    def get(self, request):
        partner = get_partner_for_site(request)

        sku = request.GET.get('sku', None)
        code = request.GET.get('code', None)

        if not sku:
            return HttpResponseBadRequest(_('No SKU provided.'))

        voucher = Voucher.objects.get(code=code) if code else None

        try:
            product = StockRecord.objects.get(partner=partner, partner_sku=sku).product
        except StockRecord.DoesNotExist:
            return HttpResponseBadRequest(_('SKU [{sku}] does not exist.').format(sku=sku))

        if voucher is None:
            # Find and apply the enterprise entitlement on the learner basket
            voucher = get_entitlement_voucher(request, product)

        # If the product isn't available then there's no reason to continue with the basket addition
        purchase_info = request.strategy.fetch_for_product(product)
        if not purchase_info.availability.is_available_to_buy:
            msg = _('Product [{product}] not available to buy.').format(product=product.title)
            return HttpResponseBadRequest(msg)

        # If the product is not an Enrollment Code, we check to see if the user is already
        # enrolled to prevent double-enrollment and/or accidental coupon usage
        if product.get_product_class().name != ENROLLMENT_CODE_PRODUCT_CLASS_NAME:
            try:
                if request.user.is_user_already_enrolled(request, product):
                    logger.warning(
                        'User [%s] attempted to repurchase the [%s] seat of course [%s]',
                        request.user.username,
                        mode_for_seat(product),
                        product.attr.course_key
                    )
                    msg = _('You are already enrolled in {course}.').format(course=product.course.name)
                    return HttpResponseBadRequest(msg)
            except (ConnectionError, SlumberBaseException, Timeout):
                msg = _('An error occurred while retrieving enrollment details. Please try again.')
                return HttpResponseBadRequest(msg)

        # At this point we're either adding an Enrollment Code product to the basket,
        # or the user is adding a Seat product for which they are not already enrolled
        prepare_basket(request, product, voucher)
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
        if product.get_product_class().name == SEAT_PRODUCT_CLASS_NAME:
            seat_type = get_certificate_type_display_value(product.attr.certificate_type)
        elif product.get_product_class().name == ENROLLMENT_CODE_PRODUCT_CLASS_NAME:
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
            product_class_name = line.product.get_product_class().name
            if product_class_name == 'Seat':
                line_data = self._get_course_data(line.product)
                if (getattr(line.product.attr, 'id_verification_required', False) and
                        line.product.attr.certificate_type != 'credit'):
                    display_verification_message = True
                    order_details_msg = _(
                        'You will be automatically enrolled in the course upon completing your order.'
                    )
            elif product_class_name == 'Enrollment Code':
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
                'enrollment_code': line.product.get_product_class().name == ENROLLMENT_CODE_PRODUCT_CLASS_NAME,
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

            today = datetime.today()
            return {
                'client_side_payment_processor_name': payment_processor.NAME,
                'enable_client_side_checkout': True,
                'months': range(1, 13),
                'payment_form': PaymentForm(
                    user=self.request.user, initial={'basket': self.request.basket}, label_suffix=''
                ),
                'payment_url': payment_processor.client_side_payment_url,
                'paypal_enabled': 'paypal' in (p.NAME for p in payment_processors),
                # Assumption is that the credit card duration is 15 years
                'years': range(today.year, today.year + 16)
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

        context_updates, lines_data = self._process_basket_lines(lines)
        context.update(context_updates)

        course_key = lines_data[0].get('course_key') if len(lines) == 1 else None
        user = self.request.user
        context.update({
            'analytics_data': prepare_analytics_data(
                user,
                site_configuration.segment_key,
                unicode(course_key)
            ),
            'enable_client_side_checkout': False,
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
            'course_key': course_key,
            'formset_lines_data': zip(formset, lines_data),
            'free_basket': context['order_total'].incl_tax == 0,
            'homepage_url': get_lms_url(''),
            'min_seat_quantity': 1,
            'payment_processors': payment_processors,
            'total_benefit': total_benefit
        })
        return context


class VoucherAddMessagesView(VoucherAddView):
    """
    View that applies a voucher to basket.
    We change default messages oscar returns.
    """

    def form_valid(self, form):
        super(VoucherAddMessagesView, self).form_valid(form)

        code = form.cleaned_data['code']

        for msg in list(messages.get_messages(self.request)):
            if msg.message == _("No voucher found with code '{code}'").format(code=code):
                messages.error(
                    self.request,
                    _("Coupon code '{code}' does not exist.").format(code=code)
                )
            elif msg.message == _("You have already added the '{code}' voucher to your basket").format(code=code):
                messages.error(
                    self.request,
                    _("You have already added coupon code '{code}' to your basket.").format(code=code)
                )
            elif msg.message == _("The '{code}' voucher has expired").format(code=code):
                messages.error(
                    self.request,
                    _("Coupon code '{code}' has expired.").format(code=code)
                )
            elif msg.message == _("Voucher '{code}' added to basket").format(code=code):
                messages.info(
                    self.request,
                    _("Coupon code '{code}' added to basket.").format(code=code)
                )
            elif msg.message == _("Your basket does not qualify for a voucher discount"):
                messages.warning(
                    self.request,
                    _("Your basket does not qualify for a coupon code discount.")
                )
            elif msg.message == _("This voucher has already been used"):
                messages.error(
                    self.request,
                    _("Coupon code '{code}' has already been redeemed.").format(code=code)
                )
            else:
                messages.error(
                    self.request,
                    _("Coupon code '{code}' is invalid.").format(code=code)
                )

        return redirect_to_referrer(self.request, 'basket:summary')


class VoucherRemoveMessagesView(VoucherRemoveView):
    def post(self, request, *args, **kwargs):
        # This will fix the bug in Django Oscar
        # Expected Primary Key to be integer, but it's Unicode instead
        kwargs['pk'] = int(kwargs['pk'])
        return super(VoucherRemoveMessagesView, self).post(request, *args, **kwargs)
