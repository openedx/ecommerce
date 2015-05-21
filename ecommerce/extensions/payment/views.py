""" Views for interacting with the payment processor. """
import logging

from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View
from oscar.apps.order.exceptions import UnableToPlaceOrder
from oscar.apps.partner import strategy
from oscar.apps.payment.exceptions import PaymentError
from oscar.core.loading import get_class, get_model

from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.payment.exceptions import InvalidSignatureError
from ecommerce.extensions.payment.processors.cybersource import Cybersource
from ecommerce.extensions.payment.processors.paypal import Paypal

logger = logging.getLogger(__name__)

Basket = get_model('basket', 'Basket')
BillingAddress = get_model('order', 'BillingAddress')
Country = get_model('address', 'Country')
NoShippingRequired = get_class('shipping.methods', 'NoShippingRequired')
OrderTotalCalculator = get_class('checkout.calculators', 'OrderTotalCalculator')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')


class CybersourceNotifyView(EdxOrderPlacementMixin, View):
    """ Validates a response from CyberSource and processes the associated basket/order appropriately. """
    payment_processor = Cybersource()

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super(CybersourceNotifyView, self).dispatch(request, *args, **kwargs)

    def _get_billing_address(self, cybersource_response):
        return BillingAddress(
            first_name=cybersource_response['req_bill_to_forename'],
            last_name=cybersource_response['req_bill_to_surname'],
            line1=cybersource_response['req_bill_to_address_line1'],

            # Address line 2 is optional
            line2=cybersource_response.get('req_bill_to_address_line2', ''),

            # Oscar uses line4 for city
            line4=cybersource_response['req_bill_to_address_city'],
            postcode=cybersource_response['req_bill_to_address_postal_code'],
            state=cybersource_response['req_bill_to_address_state'],
            country=Country.objects.get(
                iso_3166_1_a2=cybersource_response['req_bill_to_address_country']))

    def _get_basket(self, basket_id):
        if not basket_id:
            return None

        try:
            basket_id = int(basket_id)
            basket = Basket.objects.get(id=basket_id)
            basket.strategy = strategy.Default()
            return basket
        except (ValueError, ObjectDoesNotExist):
            return None

    def post(self, request):
        """ Handle the response we've been given from the processor. """

        # Note (CCB): Orders should not be created until the payment processor has validated the response's signature.
        # This validation is performed in the handle_payment method. After that method succeeds, the response can be
        # safely assumed to have originated from CyberSource.
        cybersource_response = request.POST.dict()
        basket = None
        transaction_id = None

        try:
            transaction_id = cybersource_response.get('transaction_id')
            basket_id = cybersource_response.get('req_reference_number')

            basket = self._get_basket(basket_id)

            if not basket:
                logger.error('Received payment for non-existent basket [%s].', basket_id)
                return HttpResponse()
        finally:
            # Store the response in the database regardless of its authenticity.
            ppr = self.payment_processor.record_processor_response(cybersource_response, transaction_id=transaction_id,
                                                                   basket=basket)

        try:
            self.handle_payment(cybersource_response, basket)
        except InvalidSignatureError:
            logger.exception(
                'Received an invalid CyberSource response. The payment response was recorded in entry [%d].', ppr.id)
            return HttpResponse(status=400)
        except PaymentError:
            logger.exception(
                'CyberSource payment failed for basket [%d]. The payment response was recorded in entry [%d].',
                basket.id, ppr.id)
            return HttpResponse()

        # Note (CCB): In the future, if we do end up shipping physical products, we will need to properly implement
        # shipping methods. See http://django-oscar.readthedocs.org/en/latest/howto/how_to_configure_shipping.html.
        shipping_method = NoShippingRequired()
        shipping_charge = shipping_method.calculate(basket)

        # Note (CCB): This calculation assumes the payment processor has not sent a partial authorization, thus we use
        # the amounts stored in the database rather than those received from the payment processor.
        order_total = OrderTotalCalculator().calculate(basket, shipping_charge)

        billing_address = self._get_billing_address(cybersource_response)

        try:
            user = basket.owner
            order_number = self.generate_order_number(basket)
            self.handle_order_placement(order_number, user, basket, None, shipping_method, shipping_charge,
                                        billing_address, order_total)
        except UnableToPlaceOrder:
            logger.exception('Payment was received, but an order was not created for basket [%d].', basket.id)
            # Ensure we return, in case future changes introduce post-order placement functionality.
            return HttpResponse()

        return HttpResponse()


class PaypalPaymentExecutionView(EdxOrderPlacementMixin, View):
    """Execute an approved PayPal payment and place an order for paid products as appropriate."""
    payment_processor = Paypal()

    def _get_basket(self, payment_id):
        """Retrieve a basket using a payment ID."""
        basket = PaymentProcessorResponse.objects.get(
            processor_name=self.payment_processor.NAME,
            transaction_id=payment_id
        ).basket

        basket.strategy = strategy.Default()

        return basket

    def get(self, request):
        """Handle an incoming user returned to us by PayPal after approving payment."""
        payment_id = request.GET.get('paymentId')
        payer_id = request.GET.get('PayerID')
        logger.info(u"Payment [%s] approved by payer [%s]", payment_id, payer_id)

        paypal_response = request.GET.dict()
        basket = self._get_basket(payment_id)
        receipt_url = u'{}?basket_id={}'.format(self.payment_processor.receipt_url, basket.id)

        try:
            self.handle_payment(paypal_response, basket)
        except PaymentError:
            return redirect(receipt_url)

        shipping_method = NoShippingRequired()
        shipping_charge = shipping_method.calculate(basket)
        order_total = OrderTotalCalculator().calculate(basket, shipping_charge)

        try:
            user = basket.owner
            order_number = self.generate_order_number(basket)

            self.handle_order_placement(
                order_number=order_number,
                user=user,
                basket=basket,
                shipping_address=None,
                shipping_method=shipping_method,
                shipping_charge=shipping_charge,
                billing_address=None,
                order_total=order_total
            )
        except UnableToPlaceOrder:
            logger.exception('Payment was executed, but an order was not created for basket [%d].', basket.id)

        return redirect(receipt_url)
