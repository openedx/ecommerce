""" Checkout related views. """
from __future__ import unicode_literals
from decimal import Decimal

import dateutil.parser
import waffle
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import RedirectView, TemplateView
from oscar.apps.checkout.views import *  # pylint: disable=wildcard-import, unused-wildcard-import
from oscar.core.loading import get_class, get_model

from ecommerce.core.url_utils import get_ecommerce_url, get_lms_url
from ecommerce.extensions.api.serializers import OrderSerializer
from ecommerce.extensions.checkout.exceptions import BasketNotFreeError
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.checkout.utils import add_currency, get_credit_provider_details
from ecommerce.extensions.offer.utils import get_discount_percentage
from ecommerce.extensions.payment.models import PaymentProcessorResponse

Applicator = get_class('offer.utils', 'Applicator')
Basket = get_model('basket', 'Basket')
Order = get_model('order', 'Order')


class FreeCheckoutView(EdxOrderPlacementMixin, RedirectView):
    """ View to handle free checkouts.

    Retrieves the user's basket and checks to see if the basket is free in which case
    the user is redirected to the receipt page. Otherwise the user is redirected back
    to the basket summary page.
    """

    permanent = False

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(FreeCheckoutView, self).dispatch(*args, **kwargs)

    def get_redirect_url(self, *args, **kwargs):
        basket = Basket.get_basket(self.request.user, self.request.site)
        if not basket.is_empty:
            # Need to re-apply the voucher to the basket.
            Applicator().apply(basket, self.request.user, self.request)
            if basket.total_incl_tax != Decimal(0):
                raise BasketNotFreeError("Basket is not free.")

            order = self.place_free_order(basket)

            if waffle.switch_is_active('otto_receipt_page'):
                receipt_path = '{}?order_number={}'.format(settings.RECEIPT_PAGE_PATH, order.number)
                url = get_ecommerce_url(receipt_path)
            else:
                receipt_path = '{}?orderNum={}'.format('/commerce/checkout/receipt', order.number)
                url = get_lms_url(receipt_path)
        else:
            # If a user's basket is empty redirect the user to the basket summary
            # page which displays the appropriate message for empty baskets.
            url = reverse('basket:summary')
        return url


class CancelCheckoutView(TemplateView):
    """
    Displays a cancellation message when the customer cancels checkout on the
    payment processor page.
    """

    template_name = 'checkout/cancel_checkout.html'

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        """
        Request needs to be csrf_exempt to handle POST back from external payment processor.
        """
        return super(CancelCheckoutView, self).dispatch(*args, **kwargs)

    def post(self, request, *args, **kwargs):  # pylint: disable=unused-argument
        """
        Allow POST responses from payment processors and just render the cancel page..
        """
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super(CancelCheckoutView, self).get_context_data(**kwargs)
        context.update({
            'payment_support_email': self.request.site.siteconfiguration.payment_support_email,
        })
        return context


class CheckoutErrorView(TemplateView):
    """ Displays an error page when checkout does not complete successfully. """

    template_name = 'checkout/error.html'

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        """
        Request needs to be csrf_exempt to handle POST back from external payment processor.
        """
        return super(CheckoutErrorView, self).dispatch(*args, **kwargs)

    def post(self, request, *args, **kwargs):  # pylint: disable=unused-argument
        """
        Allow POST responses from payment processors and just render the error page.
        """
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super(CheckoutErrorView, self).get_context_data(**kwargs)
        context.update({
            'payment_support_email': self.request.site.siteconfiguration.payment_support_email,
        })
        return context


class ReceiptResponseView(TemplateView):
    """ Handles behavior needed to display an order receipt. """

    template_name = 'checkout/receipt.html'

    @method_decorator(csrf_exempt)
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        """
        Customers should only be able to view their receipts when logged in. To avoid blocking responses
        from payment processors which POST back to the page, the view must be CSRF-exempt.
        """
        return super(ReceiptResponseView, self).dispatch(*args, **kwargs)

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)

        order_number = self.request.GET.get('order_number')
        if order_number:
            try:
                order = Order.objects.get(number=order_number, user=self.request.user)
            except Order.DoesNotExist:
                context.update({
                    'error_text': _('Order {order_number} not found.').format(order_number=order_number),
                    'for_help_text': '',
                    'is_payment_complete': False,
                    'page_title': _('Order not found')
                })
                return self.render_to_response(context)

            seat = order.lines.first().product
            course = self.request.site.siteconfiguration.course_catalog_api_client.course_runs(seat.attr.course_key).get()
            provider_data = None
            if seat.attr.certificate_type == 'credit':
                provider_data = get_credit_provider_details(
                    access_token=self.request.user.access_token,
                    credit_provider_id=seat.attr.credit_provider,
                    site_configuration=self.request.site.siteconfiguration
                )

            order_data = OrderSerializer(order, context={'request': self.request}).data
            discount_value = float(order_data['discount'])
            total_cost = float(order_data['total_excl_tax'])
            original_cost = discount_value + total_cost

            try:
                recipient_info = PaymentProcessorResponse.objects.filter(
                    basket=order.basket
                ).latest().response['payer']
            except (PaymentProcessorResponse.DoesNotExist, KeyError):
                recipient_info = None

            receipt = {
                'billed_to': recipient_info,
                'currency': settings.OSCAR_DEFAULT_CURRENCY,
                'discount': add_currency(discount_value),
                'discount_percentage': get_discount_percentage(
                    discount_value=discount_value,
                    product_price=original_cost
                ),
                'email': order.user.email,
                'is_refunded': False,
                'items': [{
                    'description': line['description'],
                    'cost': add_currency(float(line['line_price_excl_tax'])),
                    'quantity': line['quantity']
                } for line in order_data['lines']],
                'order_number': order.number,
                'original_cost': add_currency(original_cost),
                'payment_processor': order_data['payment_processor'],
                'purchased_datetime': dateutil.parser.parse(order_data['date_placed']).strftime('%d. %B %Y'),
                'total_cost': add_currency(total_cost),
                'vouchers': order_data['vouchers']
            }

            context.update({
                'course': course,
                'is_verification_required': seat.attr.id_verification_required,
                'lms_url': order.site.siteconfiguration.lms_url_root,
                'provider_data': provider_data,
                'receipt': receipt,
                'verified': seat.attr.certificate_type == 'verified'
            })
        else:
            context.update({
                'error_text': _('Order number is invalid.'),
                'for_help_text': '',
                'is_payment_complete': False,
                'page_title': _('Invalid order number')
            })

        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):  # pylint: disable=unused-argument
        context = self.get_context_data(**kwargs)
        # CyberSource responses will indicate whether a payment failed due to a transaction on their end. In this case,
        # we can provide the learner more detailed information in the error message.
        if request.POST['decision'] != 'ACCEPT':
            context.update({
                'is_payment_complete': False,
                'page_title': _('Payment Failed'),
                'error_summary': _('A system error occurred while processing your payment. You have not been charged.'),
                'error_text': _('Please wait a few minutes and then try again.'),
                'for_help_text': _(
                    'For help, contact {payment_support_link}.'
                ).format(payment_support_link=context['payment_support_link'])
            })
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super(ReceiptResponseView, self).get_context_data(**kwargs)

        payment_support_email = self.request.site.siteconfiguration.payment_support_email
        payment_support_link = '<a href="mailto:{email}">{email}</a>'.format(email=payment_support_email)

        context.update({
            'dashboard': get_lms_url('/dashboard'),
            'error_summary': _('An error occurred while creating your receipt.'),
            'error_text': None,
            'for_help_text': _(
                "If your course does not appear on your dashboard, contact {payment_support_link}."
            ).format(payment_support_link=payment_support_link),
            'is_payment_complete': True,
            'lms_url': get_lms_url(),
            'name': '{} {}'.format(self.request.user.first_name, self.request.user.last_name),
            'nav_hidden': True,
            'page_title': _('Receipt'),
            'payment_support_email': payment_support_email,
            'payment_support_link': payment_support_link,
            'platform_name': settings.SITE_NAME,
            'verify_link': get_lms_url('/verify_student/verify-now/')
        })

        return context
