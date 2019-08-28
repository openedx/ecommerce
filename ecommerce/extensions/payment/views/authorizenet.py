""" View for interacting with the payment processor. """

from __future__ import unicode_literals

import base64
import json
import logging
from django.db import transaction
from django.http import HttpResponse
from django.views.generic import View
from django.shortcuts import redirect
from oscar.apps.partner import strategy
from django.utils.decorators import method_decorator
from oscar.core.loading import get_class, get_model
from ecommerce.extensions.payment.exceptions import (
    InvalidBasketError,
    MissingTransactionDetailError
)
from oscar.apps.payment.exceptions import TransactionDeclined
from ecommerce.core.url_utils import get_lms_dashboard_url
from ecommerce.notifications.notifications import send_notification
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.payment.processors.authorizenet import AuthorizeNet

logger = logging.getLogger(__name__)

Applicator = get_class('offer.applicator', 'Applicator')
Basket = get_model('basket', 'Basket')
BillingAddress = get_model('order', 'BillingAddress')
Country = get_model('address', 'Country')
NoShippingRequired = get_class('shipping.methods', 'NoShippingRequired')
OrderNumberGenerator = get_class('order.utils', 'OrderNumberGenerator')
OrderTotalCalculator = get_class('checkout.calculators', 'OrderTotalCalculator')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')

NOTIFICATION_TYPE_AUTH_CAPTURE_CREATED = "net.authorize.payment.authcapture.created"

class AuthorizeNetNotificationView(EdxOrderPlacementMixin, View):
    """
        Execute an approved AuthorizeNet payment and place an order for paid products.
    """

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

    def _send_transaction_declined_email(self, basket, transaction_status, course_title):
        """
            send email to the user after receiving a transcation notification with
            decilened/error status.

            Arguments:
                basket: transaction relevant basket.
                transaction_status: Error or Declined.
                course_title: course for which transaction was performed.
        """
        send_notification(
            basket.owner,
            'TRANSACTION_REJECTED',
            {
                'course_title': course_title,
                'transaction_status': transaction_status,
            },
            basket.site
        )

    def _get_basket(self, basket_id):
        """
            Retrieve a basket using a basket Id.

            Arguments:
                payment_id: payment_id received from AuthorizeNet.
            Returns:
                It will return related basket
        """
        if not basket_id:
            return None

        try:
            basket = Basket.objects.get(id=basket_id)
            basket.strategy = strategy.Default()
            return basket
        except (ValueError, ObjectDoesNotExist):
            return None

    def _get_billing_address(self, transaction_bill, order_number, basket):
        """
            Prepare and return a billing address object using transaction billing information.

            Arguments:
                transaction_bill: bill information from AuthorizeNet transaction response.
                order_number: related order number
            Returns:
                It will return billing object
        """
        try:
            billing_address = BillingAddress(
                first_name=str(getattr(transaction_bill, 'firstName', '')),
                last_name=str(getattr(transaction_bill, 'lastName', '')),
                line1=str(getattr(transaction_bill, 'address', '')),
                line4=str(getattr(transaction_bill, 'city', '')),  # Oscar uses line4 for city
                state=str(getattr(transaction_bill, 'state', '')),
                country=Country.objects.get(
                    iso_3166_1_a2__iexact=transaction_bill.country
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

    def _call_handle_order_placement(self, basket, request, transaction_details):
        """
            Handle order placement for approved transactions.
        """
        try:
            shipping_method = NoShippingRequired()
            shipping_charge = shipping_method.calculate(basket)
            order_total = OrderTotalCalculator().calculate(basket, shipping_charge)

            user = basket.owner
            order_number = str(transaction_details.transaction.order.invoiceNumber)

            billing_address = self._get_billing_address(
                transaction_details.transaction.billTo, order_number, basket)

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

    def post(self, request):
        """
            This view will be called by AuthorizeNet to handle notifications and order placement.
            It should return 200 (to Authorizenet) after receiving a notification so they'll know
            that notification has been received at our end otherwise they will send it again and
            again after the particular interval.
        """
        course_id = None
        notification = request.POST
        if notification.get("eventType") != NOTIFICATION_TYPE_AUTH_CAPTURE_CREATED:
            logger.error('Received AuthroizeNet notifciation with event_type [%s]. Currently, We are not handling \
            such type of notifications.', notification.get("eventType"))
            return HttpResponse(status=204)

        notification_id = notification.get("notificationId")
        payload = notification.get("payload", {})

        transaction_id = payload.get("id")
        if not transaction_id:
            logger.error(
                'Recieved AuthorizeNet transaction notification without transaction_id',
            )
            return HttpResponse(status=400)

        try:
            transaction_details = self.payment_processor.get_transaction_detail(transaction_id)

            if not transaction_details:
                logger.error('Unable to get Authorizenet transaction detail using transaction_id [%s].', transaction_id)
                raise MissingTransactionDetailError

            order_number = str(transaction_details.transaction.order.invoiceNumber)
            basket_id = OrderNumberGenerator().basket_id(order_number)

            logger.info(
                'Received AuthorizeNet payment notification for transaction [%s], associated with basket [%d].',
                transaction_id,
                basket_id
            )

            basket = self._get_basket(basket_id)

            if not basket:
                logger.error('Received AuthorizeNet payment notification for non-existent basket [%s].', basket_id)
                raise InvalidBasketError

            if basket.status != Basket.FROZEN:
                logger.info(
                    'Received AuthorizeNet payment notification for basket [%d] which is in a non-frozen state, [%s]',
                    basket.id, basket.status
                )

            self.payment_processor.record_processor_response(
                notification, transaction_id=notification_id, basket=basket
            )

            product = basket.all_lines()[0].product
            course_id = product.course_id
            if payload.get("responseCode") != 1:
                transaction_status = "Declined" if payload.get("responseCode") == 2 else "Error"
                logger.error(
                    'AuthorizeNet transaction of transaction_id [%s] associated with basket [%s] has \
                    been rejected with status: [%s].',
                    transaction_id,
                    basket_id,
                    transaction_status
                )
                course_title = product.title
                self._send_transaction_declined_email(basket, transaction_status, course_title)

            else:
                with transaction.atomic():
                    self.handle_payment(transaction_details, basket)
                    self._call_handle_order_placement(basket, request, transaction_details)

        except Exception:
            logger.exception('An error occurred while processing the AuthorizeNet \
                payment for basket [%d].', basket.id)
        finally:
            return HttpResponse(status=200)

def handle_redirection(request):
    """
        Handle AuthorizeNet redirection. This view will be called when a user clicks on continue button
        from AuthorizeNet receipt page. It will handle Transaction cookie named as "pendingTransactionCourse".
        Transaction cookie should contain encrypted course id for which transaction has been performed butq
        notification is yet to be received. This cookie will be used at LMS-side to display waiting
        alert to the user.
    """
    lms_dashboard = get_lms_dashboard_url()
    response = redirect(lms_dashboard)

    course_id_hash = request.GET.get('course')
    if course_id_hash:
        response.set_cookie('pendingTransactionCourse', course_id_hash)

    return response
