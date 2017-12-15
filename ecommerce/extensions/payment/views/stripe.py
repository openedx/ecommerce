import logging

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import ugettext as _
from oscar.apps.payment.exceptions import TransactionDeclined
from oscar.core.loading import get_class, get_model

from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.checkout.utils import get_receipt_page_url
from ecommerce.extensions.payment.forms import StripeSubmitForm, StripeSubmitSourceForm
from ecommerce.extensions.payment.processors.stripe import Stripe
from ecommerce.extensions.payment.views import BasePaymentSubmitView

logger = logging.getLogger(__name__)

Applicator = get_class('offer.utils', 'Applicator')
BillingAddress = get_model('order', 'BillingAddress')
Country = get_model('address', 'Country')
NoShippingRequired = get_class('shipping.methods', 'NoShippingRequired')
OrderTotalCalculator = get_class('checkout.calculators', 'OrderTotalCalculator')


class StripeSubmitView(EdxOrderPlacementMixin, BasePaymentSubmitView):
    """ Stripe payment handler.

    The payment form should POST here. This view will handle creating the charge at Stripe, creating an order,
    and redirecting the user to the receipt page.
    """
    form_class = StripeSubmitForm

    @property
    def payment_processor(self):
        return Stripe(self.request.site)

    def form_valid(self, form):
        form_data = form.cleaned_data
        basket = form_data['basket']
        token = form_data['stripe_token']
        order_number = basket.order_number

        try:
            billing_address = self.payment_processor.get_address_from_token(token)
        except Exception:  # pylint: disable=broad-except
            logger.exception(
                'An error occurred while parsing the billing address for basket [%d]. No billing address will be '
                'stored for the resulting order [%s].',
                basket.id,
                order_number)
            billing_address = None

        try:
            self.handle_payment(token, basket)
        except Exception:  # pylint: disable=broad-except
            logger.exception('An error occurred while processing the Stripe payment for basket [%d].', basket.id)
            return JsonResponse({}, status=400)

        shipping_method = NoShippingRequired()
        shipping_charge = shipping_method.calculate(basket)
        order_total = OrderTotalCalculator().calculate(basket, shipping_charge)

        self.handle_order_placement(
            order_number=order_number,
            user=basket.owner,
            basket=basket,
            shipping_address=None,
            shipping_method=shipping_method,
            shipping_charge=shipping_charge,
            billing_address=billing_address,
            order_total=order_total,
            request=self.request
        )

        receipt_url = get_receipt_page_url(
            site_configuration=self.request.site.siteconfiguration,
            order_number=order_number
        )
        return JsonResponse({'url': receipt_url}, status=201)


class StripeSubmitSourceView(EdxOrderPlacementMixin, BasePaymentSubmitView):
    form_class = StripeSubmitSourceForm
    http_method_names = ['get', 'options']

    def get(self, request):
        return self.post(request)

    def get_form_kwargs(self):
        return {
            'data': self.request.GET,
            'user': self.request.user,
            'request': self.request,
        }

    @property
    def payment_processor(self):
        return Stripe(self.request.site)

    def form_valid(self, form):
        form_data = form.cleaned_data
        basket = form_data['basket']
        source = form_data['source']
        order_number = basket.order_number

        try:
            self.handle_payment(source, basket)
        except TransactionDeclined:
            messages.add_message(self.request, messages.WARNING, _('Your payment was declined. Please try again.'))
            return redirect(reverse('basket:summary'))

        shipping_method = NoShippingRequired()
        shipping_charge = shipping_method.calculate(basket)
        order_total = OrderTotalCalculator().calculate(basket, shipping_charge)

        self.handle_order_placement(
            order_number=order_number,
            user=basket.owner,
            basket=basket,
            shipping_address=None,
            shipping_method=shipping_method,
            shipping_charge=shipping_charge,
            billing_address=None,
            order_total=order_total,
            request=self.request
        )

        receipt_url = get_receipt_page_url(
            site_configuration=self.request.site.siteconfiguration,
            order_number=order_number
        )

        return redirect(receipt_url, permanent=False)
