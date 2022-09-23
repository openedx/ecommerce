

import logging

from django.core.exceptions import MultipleObjectsReturned
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect
from oscar.apps.partner import strategy
from oscar.apps.payment.exceptions import PaymentError
from oscar.core.loading import get_class, get_model
from rest_framework.decorators import action
from rest_framework.response import Response

from ecommerce.extensions.basket.utils import basket_add_organization_attribute, basket_add_payment_intent_id_attribute
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
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')


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
        payment_intent_id = form_data['payment_intent_id']
        order_number = basket.order_number

        basket_add_organization_attribute(basket, self.request.POST)
        basket_add_payment_intent_id_attribute(basket, self.request.POST)

        try:
            self.handle_payment(payment_intent_id, basket)
        except Exception:  # pylint: disable=broad-except
            logger.exception('An error occurred while processing the Stripe payment for basket [%d].', basket.id)
            return JsonResponse({}, status=400)

        try:
            order = self.create_order(self.request, basket)
        except Exception:  # pylint: disable=broad-except
            logger.exception('An error occurred while processing the Stripe payment for basket [%d].', basket.id)
            return JsonResponse({}, status=400)

        self.handle_post_order(order)

        receipt_url = get_receipt_page_url(
            self.request,
            site_configuration=self.request.site.siteconfiguration,
            order_number=order_number,
            disable_back_button=True
        )
        return JsonResponse({'url': receipt_url}, status=201)


class StripeCheckoutView(EdxOrderPlacementMixin, BasePaymentSubmitView):
    http_method_names = ['get', 'post', 'head']

    @property
    def payment_processor(self):
        return Stripe(self.request.site)
    
    def _get_basket(self, payment_intent_id):
        """
        Retrieve a basket using a payment intent ID.

        Arguments:
            payment_intent_id: payment_intent_id received from Stripe.

        Returns:
            It will return related basket or log exception and return None if
            duplicate payment_intent_id* received or any other exception occurred.
        """
        try:
            ppr = PaymentProcessorResponse.objects.get(
                processor_name=self.payment_processor.NAME,
                transaction_id=payment_intent_id,
            )
            basket = ppr.basket
            basket.strategy = strategy.Default()

            Applicator().apply(basket, basket.owner, self.request)

            ## TODO: do we need to do this?
            # basket_add_organization_attribute(basket, self.request.GET)
        except MultipleObjectsReturned:
            logger.warning(u"Duplicate payment_intent_id [%s] received from Stripe.", payment_intent_id)
            return None
        except Exception:  # pylint: disable=broad-except
            logger.exception(u"Unexpected error during basket retrieval while executing Stripe payment.")
            return None
        return basket

    def get(self, request):
        """Handle an incoming user returned to us by Stripe after approving payment."""
        # ?payment_intent=pi_3LkunSIadiFyUl1x0KT2BWzv&payment_intent_client_secret=pi_3LkunSIadiFyUl1x0KT2BWzv_secret_LYOAHVmb3H3GUdkoISSDG3ilF&redirect_status=succeeded
        payment_intent_id = request.GET.get('payment_intent')
        # we're gonna want to check the $$ price of paymentIntentId
        # to see if it suceeded or failed
        # ... and then potentially compare it against what our basket has? TBD
        stripe_response = request.GET.dict()
        basket = self._get_basket(payment_intent_id)

        if not basket:
            return redirect(self.payment_processor.error_url)

        receipt_url = get_receipt_page_url(
            self.request,
            order_number=basket.order_number,
            site_configuration=basket.site.siteconfiguration,
            disable_back_button=True
        )

        try:
            with transaction.atomic():
                try:
                    self.handle_payment(stripe_response, basket)
                except PaymentError:
                    return redirect(self.payment_processor.error_url)
        except:  # pylint: disable=bare-except
            logger.exception('Attempts to handle payment for basket [%d] failed.', basket.id)
            return redirect(receipt_url)

        try:
            order = self.create_order(request, basket)
        except Exception:  # pylint: disable=broad-except
            # any errors here will be logged in the create_order method. If we wanted any
            # Paypal specific logging for this error, we would do that here.
            return redirect(receipt_url)

        try:
            self.handle_post_order(order)
        except Exception:  # pylint: disable=broad-except
            self.log_order_placement_exception(basket.order_number, basket.id)

        return redirect(receipt_url)
