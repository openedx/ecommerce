""" Views for interacting with the payment processor. """
from __future__ import absolute_import, unicode_literals

import logging
import os

import waffle
from django.core.exceptions import MultipleObjectsReturned
from django.core.management import call_command
from django.db import transaction
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.utils.six import StringIO
from django.views.generic import View
from edx_rest_api_client.client import EdxRestApiClient
from edx_rest_api_client.exceptions import SlumberHttpBaseException
from oscar.apps.partner import strategy
from oscar.apps.payment.exceptions import PaymentError
from oscar.core.loading import get_class, get_model
from requests.exceptions import Timeout

from ecommerce.core.url_utils import get_lms_url
from ecommerce.extensions.basket.utils import basket_add_organization_attribute
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.checkout.utils import get_receipt_page_url
from ecommerce.extensions.fulfillment.status import ORDER
from ecommerce.extensions.offer.constants import DYNAMIC_DISCOUNT_FLAG
from ecommerce.extensions.payment.processors.paypal import Paypal

logger = logging.getLogger(__name__)

Applicator = get_class('offer.applicator', 'Applicator')
Basket = get_model('basket', 'Basket')
BillingAddress = get_model('order', 'BillingAddress')
Country = get_model('address', 'Country')
NoShippingRequired = get_class('shipping.methods', 'NoShippingRequired')
Order = get_model('order', 'Order')
OrderNumberGenerator = get_class('order.utils', 'OrderNumberGenerator')
OrderTotalCalculator = get_class('checkout.calculators', 'OrderTotalCalculator')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')


class PaypalPaymentExecutionView(EdxOrderPlacementMixin, View):
    """Execute an approved PayPal payment and place an order for paid products as appropriate."""

    @property
    def payment_processor(self):
        return Paypal(self.request.site)

    # Disable atomicity for the view. Otherwise, we'd be unable to commit to the database
    # until the request had concluded; Django will refuse to commit when an atomic() block
    # is active, since that would break atomicity. Without an order present in the database
    # at the time fulfillment is attempted, asynchronous order fulfillment tasks will fail.
    @method_decorator(transaction.non_atomic_requests)
    def dispatch(self, request, *args, **kwargs):
        return super(PaypalPaymentExecutionView, self).dispatch(request, *args, **kwargs)

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
            # TODO: Remove as a part of REVMI-124 as this is a hacky solution
            # The problem is that orders are being created after payment processing, and the discount is not
            # saved in the database, so it needs to be calculated again in order to save the correct info to the
            # order. REVMI-124 will create the order before payment processing, when we have the discount context.
            if waffle.flag_is_active(self.request, DYNAMIC_DISCOUNT_FLAG) and basket.lines.count() == 1:
                discount_lms_url = get_lms_url('/api/discounts/')
                lms_discount_client = EdxRestApiClient(discount_lms_url,
                                                       jwt=self.request.site.siteconfiguration.access_token)
                ck = basket.lines.first().product.course_id
                user_id = basket.owner.lms_user_id
                try:
                    response = lms_discount_client.user(user_id).course(ck).get()
                    self.request.GET = self.request.GET.copy()
                    self.request.GET['discount_jwt'] = response.get('jwt')
                except (SlumberHttpBaseException, Timeout) as error:
                    logger.warning(
                        'Failed to get discount jwt from LMS. [%s] returned [%s]',
                        discount_lms_url,
                        error.response)
            # END TODO

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
        """Handle an incoming user returned to us by PayPal after approving payment."""
        payment_id = request.GET.get('paymentId')
        payer_id = request.GET.get('PayerID')
        logger.info(u"Payment [%s] approved by payer [%s]", payment_id, payer_id)

        paypal_response = request.GET.dict()
        basket = self._get_basket(payment_id)

        if not basket:
            return redirect(self.payment_processor.error_url)

        receipt_url = get_receipt_page_url(
            order_number=basket.order_number,
            site_configuration=basket.site.siteconfiguration,
            disable_back_button=True,
        )

        order = Order.objects.get(number=basket.order_number)
        try:
            with transaction.atomic():
                try:
                    self.handle_payment(paypal_response, basket)
                except PaymentError:
                    order.set_status(ORDER.PAYMENT_FAILED)
                    return redirect(self.payment_processor.error_url)
        except:  # pylint: disable=bare-except
            # FIXME-BB: Did it really fail? If so, why are we going to the receipt page?
            order.set_status(ORDER.PAYMENT_FAILED)
            logger.exception('Attempts to handle payment for basket [%d] failed.', basket.id)
            return redirect(receipt_url)

        # Set Order to Open on a successful payment
        # FIXME-BB: Do we need to set the order to open here? Should be set to open in record_payment right?
        order.set_status(ORDER.OPEN)
        return redirect(receipt_url)


class PaypalProfileAdminView(View):
    ACTIONS = ('list', 'create', 'show', 'update', 'delete', 'enable', 'disable')

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            raise Http404

        return super(PaypalProfileAdminView, self).dispatch(request, *args, **kwargs)

    def get(self, request, *_args, **_kwargs):

        # Capture all output and logging
        out = StringIO()
        err = StringIO()
        log = StringIO()

        log_handler = logging.StreamHandler(log)
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        log_handler.setFormatter(formatter)
        logger.addHandler(log_handler)

        action = request.GET.get('action')
        if action not in self.ACTIONS:
            return HttpResponseBadRequest("Invalid action.")
        profile_id = request.GET.get('id', '')
        json_str = request.GET.get('json', '')

        command_params = [action]
        if action in ('show', 'update', 'delete', 'enable', 'disable'):
            command_params.append(profile_id.strip())
        if action in ('create', 'update'):
            command_params.append(json_str.strip())

        logger.info("user %s is managing paypal profiles: %s", request.user.username, command_params)

        success = False
        try:
            call_command('paypal_profile', *command_params,
                         settings=os.environ['DJANGO_SETTINGS_MODULE'], stdout=out, stderr=err)
            success = True
        except:  # pylint: disable=bare-except
            # we still want to present the output whether or not the command succeeded.
            pass

        # Format the output for display
        output = u'STDOUT\n{out}\n\nSTDERR\n{err}\n\nLOG\n{log}'.format(out=out.getvalue(), err=err.getvalue(),
                                                                        log=log.getvalue())

        # Remove the log capture handler
        logger.removeHandler(log_handler)

        return HttpResponse(output, content_type='text/plain', status=200 if success else 500)
