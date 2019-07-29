""" Views for interacting with the payment processor. """
from __future__ import unicode_literals

import logging
import os
from cStringIO import StringIO
from django.http import JsonResponse

from django.core.exceptions import MultipleObjectsReturned
from django.core.management import call_command
from django.db import transaction
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.generic import View
from oscar.apps.partner import strategy
from oscar.apps.payment.exceptions import PaymentError
from oscar.core.loading import get_class, get_model

from ecommerce.extensions.basket.utils import basket_add_organization_attribute
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.checkout.utils import get_receipt_page_url
from ecommerce.extensions.payment.processors.authorizenet import AuthorizeNet

from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse


logger = logging.getLogger(__name__)

Applicator = get_class('offer.applicator', 'Applicator')
Basket = get_model('basket', 'Basket')
BillingAddress = get_model('order', 'BillingAddress')
Country = get_model('address', 'Country')
NoShippingRequired = get_class('shipping.methods', 'NoShippingRequired')
OrderNumberGenerator = get_class('order.utils', 'OrderNumberGenerator')
OrderTotalCalculator = get_class('checkout.calculators', 'OrderTotalCalculator')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')

from django.shortcuts import render


@csrf_exempt
def testView(request):
    return HttpResponse('')

def render_communicator(request):
    return render(request,'payment/authorizenet-communicator.html')

class AuthorizeNetPaymentView(EdxOrderPlacementMixin, View):
    """Execute an approved authorizenet payment and place an order for paid products as appropriate."""

    @property
    def payment_processor(self):
        return AuthorizeNet(self.request.site)

    # Disable atomicity for the view. Otherwise, we'd be unable to commit to the database
    # until the request had concluded; Django will refuse to commit when an atomic() block
    # is active, since that would break atomicity. Without an order present in the database
    # at the time fulfillment is attempted, asynchronous order fulfillment tasks will fail.
    @method_decorator(transaction.non_atomic_requests)
    def dispatch(self, request, *args, **kwargs):
        return super(AuthorizeNetPaymentView, self).dispatch(request, *args, **kwargs)

    def _get_basket(self, payment_id):
        """
        Retrieve a basket using a payment ID.

        Arguments:
            payment_id: payment_id received from PayPal.

        Returns:
            It will return related basket or log exception and return None if
            duplicate payment_id received or any other exception occurred.

        """
        try:
            basket = PaymentProcessorResponse.objects.get(
                processor_name=self.payment_processor.NAME,
                transaction_id=payment_id
            ).basket
            basket.strategy = strategy.Default()
            Applicator().apply(basket, basket.owner, self.request)

            basket_add_organization_attribute(basket, self.request.GET)
            return basket
        except MultipleObjectsReturned:
            logger.warning(u"Duplicate payment ID [%s] received from PayPal.", payment_id)
            return None
        except Exception:  # pylint: disable=broad-except
            logger.exception(u"Unexpected error during basket retrieval while executing PayPal payment.")
            return None

    def get(self, request):
        """Handle an incoming user returned to us by AuthorizeNet after approving payment."""
        pass
        # data = self.payment_processor.record_response()
        # logger.info(u"Payment approved by authorizenet)

        # if not basket:
        #     return redirect(self.payment_processor.error_url)

        # receipt_url = get_receipt_page_url(
        #     order_number=basket.order_number,
        #     site_configuration=basket.site.siteconfiguration
        # )

        # try:
        #     with transaction.atomic():
        #         try:
        #             self.handle_payment({}, basket)
        #         except PaymentError:
        #             return redirect(self.payment_processor.error_url)
        # except:  # pylint: disable=bare-except
        #     logger.exception('Attempts to handle payment for basket [%d] failed.', basket.id)
        #     return redirect(receipt_url)

        # self.call_handle_order_placement(basket, request)
        # return redirect(receipt_url)

    def post(self, request):
        """Handle an incoming user returned to us by AuthorizeNet after approving payment."""
        basket_id = request.POST.get('basket')
        try:
            basket = request.user.baskets.get(id=basket_id)
        except ObjectDoesNotExist:
            return HttpResponseBadRequest('Basket [{}] not found.'.format(basket_id))

        basket.strategy = strategy.Default()
        Applicator().apply(basket, basket.owner, self.request)
        
        response = self.payment_processor.get_transaction_parameters(basket)
        return JsonResponse(response)

    def call_handle_order_placement(self, basket, request):
        pass
        # try:
        #     shipping_method = NoShippingRequired()
        #     shipping_charge = shipping_method.calculate(basket)
        #     order_total = OrderTotalCalculator().calculate(basket, shipping_charge)

        #     user = basket.owner
        #     # Given a basket, order number generation is idempotent. Although we've already
        #     # generated this order number once before, it's faster to generate it again
        #     # than to retrieve an invoice number from PayPal.
        #     order_number = basket.order_number

        #     order = self.handle_order_placement(
        #         order_number=order_number,
        #         user=user,
        #         basket=basket,
        #         shipping_address=None,
        #         shipping_method=shipping_method,
        #         shipping_charge=shipping_charge,
        #         billing_address=None,
        #         order_total=order_total,
        #         request=request
        #     )
        #     self.handle_post_order(order)

        # except Exception:  # pylint: disable=broad-except
        #     self.log_order_placement_exception(basket.order_number, basket.id)

