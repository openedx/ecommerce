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
from ecommerce.extensions.payment.processors.authorizenet import AuthorizeNet
from ecommerce.core.url_utils import get_lms_dashboard_url

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


class AuthorizeNetNotificationView(EdxOrderPlacementMixin, View):
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
        return super(AuthorizeNetNotificationView, self).dispatch(request, *args, **kwargs)

    def _get_basket(self, basket_id):
        """
        Retrieve a basket using a payment ID.

        Arguments:
            payment_id: payment_id received from PayPal.

        Returns:
            It will return related basket or log exception and return None if
            duplicate payment_id received or any other exception occurred.

        """
        if not basket_id:
            return None

        try:
            basket_id = int(basket_id)
            basket = Basket.objects.get(id=basket_id)
            basket.strategy = strategy.Default()
            Applicator().apply(basket, basket.owner, self.request)
            return basket
        except (ValueError, ObjectDoesNotExist):
            return None

    def _get_billing_address(self, transaction_billing, order_number):
        """
        Arguments:
        Returns:

        """
        try:
            import pdb; pdb.set_trace()
            billing_address = BillingAddress(
                first_name=str(transaction_billing.firstName),
                last_name=str(transaction_billing.lastName),
                line1=str(transaction_billing.address),
                line4=str(transaction_billing.city),  # Oscar uses line4 for city
                state=str(transaction_billing.state),
                country=Country.objects.get(
                    iso_3166_1_a2__iexact=transaction_billing.country
                )
            )

        except Exception:  # pylint: disable=broad-except
            logger.exception(
                'An error occurred while parsing the billing address for \
                    basket [%d]. No billing address will be stored for \
                        the resulting order [%s].',
                basket.id,
                order_number)
            billing_address = None
        
        return billing_address

    def get(self, request):
        self.post(request)

    def post(self, request):
        """Handle an incoming user returned to us by AuthorizeNet after approving payment."""
        notification = ""

        if notification.get("eventType") != "net.authorize.payment.authcapture.created":
            return HttpResponse("")

        notification_Id = notification.get("notificationId")
        payload = notification.get("payload")

        if payload.get("responseCode") != 1:
            logger.info(
                'Received Authorizenet declined transaction notification.',
            )
            return HttpResponse("")

        try:
            transaction_id = payload.get("id")
            if not transaction_id:
                logger.info(
                    'Recieve Authorizenet Notification without transaction_id',
                )
                return HttpResponse("")

            transaction_details = self.payment_processor.get_transaction_detail(transaction_id)
            order_number = str(transaction_details.transaction.order.invoiceNumber)
            basket_id = OrderNumberGenerator().basket_id(order_number)

            logger.info(
                'Received Authorizenet payment notification for transaction [%s], associated with basket [%d].',
                transaction_id,
                basket_id
            )

            basket = self._get_basket(basket_id)

            if not basket:
                logger.error('Received Authorizenet payment notification for non-existent basket [%s].', basket_id)
                raise InvalidBasketError

            if basket.status != Basket.FROZEN:
                logger.info(
                    'Received CyberSource payment notification for basket [%d] which is in a non-frozen state, [%s]',
                    basket.id, basket.status
                )
        finally:
            # Store the response in the database regardless of its authenticity.
            ppr = self.payment_processor.record_processor_response(
                notification, transaction_id=notification_Id, basket=basket
            )

        try:
            self.handle_payment(transaction_details, basket)
        except Exception:
            logger.exception('An error occurred while processing the Authorizenet \
                payment for basket [%d].', basket.id)
            return ""

        self._call_handle_order_placement(basket, request, transaction_details)
        return HttpResponse("")

    def _call_handle_order_placement(self, basket, request, transaction_details):
        try:
            shipping_method = NoShippingRequired()
            shipping_charge = shipping_method.calculate(basket)
            order_total = OrderTotalCalculator().calculate(basket, shipping_charge)

            user = basket.owner
            order_number = str(transaction_details.transaction.order.invoiceNumber)

            billing_address = self._get_billing_address(transaction_details.transaction.billTo, order_number)

            order = self.handle_order_placement(
                order_number=order_number,
                user=user,
                basket=basket,
                shipping_address=None,
                shipping_method=shipping_method,
                shipping_charge=shipping_charge,
                billing_address=billing_address,
                order_total=order_total,
                request=request
            )
            self.handle_post_order(order)

        except Exception:  # pylint: disable=broad-except
            self.log_order_placement_exception(basket.order_number, basket.id)
