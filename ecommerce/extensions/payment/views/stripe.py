

import logging

from django.http import JsonResponse
from oscar.core.loading import get_class, get_model

from ecommerce.extensions.basket.utils import basket_add_organization_attribute
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.checkout.utils import get_receipt_page_url
from ecommerce.extensions.payment.forms import StripeSubmitForm
from ecommerce.extensions.payment.processors.stripe import Stripe
from ecommerce.extensions.payment.views import BasePaymentSubmitView

logger = logging.getLogger(__name__)

Applicator = get_class('offer.applicator', 'Applicator')
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

        basket_add_organization_attribute(basket, self.request.POST)

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

        try:
            order = self.create_order(self.request, basket, billing_address=billing_address)
        except Exception:  # pylint: disable=broad-except
            logger.exception('An error occurred while processing the Stripe payment for basket [%d].', basket.id)
            return JsonResponse({}, status=400)

        self.handle_post_order(order)

        receipt_url = get_receipt_page_url(
            site_configuration=self.request.site.siteconfiguration,
            order_number=order_number,
            disable_back_button=True,
        )
        return JsonResponse({'url': receipt_url}, status=201)
