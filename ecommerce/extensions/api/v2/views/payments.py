"""HTTP endpoints for interacting with payments."""
import logging

from django.db import transaction
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy as _
from ecommerce_worker.payment.v1.tasks import process_notification
from oscar.apps.payment.exceptions import PaymentError, TransactionDeclined
from oscar.core.loading import get_class
from rest_framework import generics, status
from rest_framework.decorators import detail_route
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_extensions.cache.decorators import cache_response
import waffle

from ecommerce.extensions.api import serializers
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin


logger = logging.getLogger(__name__)

NoShippingRequired = get_class('shipping.methods', 'NoShippingRequired')
OrderNumberGenerator = get_class('order.utils', 'OrderNumberGenerator')
OrderTotalCalculator = get_class('checkout.calculators', 'OrderTotalCalculator')

PAYMENT_PROCESSOR_CACHE_KEY = 'PAYMENT_PROCESSOR_LIST'
PAYMENT_PROCESSOR_CACHE_TIMEOUT = 60 * 30


class PaymentAuthorizationView(EdxOrderPlacementMixin, APIView):
    """Authorize payment through a specified payment processor"""
    permission_classes = (IsAuthenticated,)

    @property
    def payment_processor(self):
        if not hasattr(self, '_payment_processor') or not self._payment_processor:
            payment_processor_name = self.request.data.get('payment_processor')
            payment_processors = self.request.site.siteconfiguration.get_payment_processors()
            self._payment_processor = payment_processors.get(payment_processor_name)
        return self._payment_processor

    # Disable atomicity for the view. Otherwise, we'd be unable to commit to the database
    # until the request had concluded; Django will refuse to commit when an atomic() block
    # is active, since that would break atomicity. Without an order present in the database
    # at the time fulfillment is attempted, asynchronous order fulfillment tasks will fail.
    @method_decorator(transaction.non_atomic_requests)
    def dispatch(self, request, *args, **kwargs):
        return super(PaymentAuthorizationView, self).dispatch(request, *args, **kwargs)

    def post(self, request):
        basket = request.basket
        if not self.payment_processor:
            return Response(
                {'error': _('You must specify a payment processor.')},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            authorization_data = request.data.dict()
            payment_processor_response = self.payment_processor.send_payment_authorization_request(
                basket,
                authorization_data
            )
        except PaymentError:
            return Response(
                {'error': _('Payment authorization request failed.')},
                status=status.HTTP_502_BAD_GATEWAY
            )

        # Explicitly delimit operations which will be rolled back if an exception occurs.
        with transaction.atomic():
            try:
                self.handle_payment(payment_processor_response.response, basket)
            except TransactionDeclined:
                return Response(
                    {'authorized': False, 'error': _('Your payment was declined.')},
                    status=status.HTTP_200_OK
                )

        try:
            # Note (CCB): In the future, if we do end up shipping physical products, we will need to
            # properly implement shipping methods. For more, see
            # http://django-oscar.readthedocs.org/en/latest/howto/how_to_configure_shipping.html.
            shipping_method = NoShippingRequired()
            shipping_charge = shipping_method.calculate(basket)

            # Note (CCB): This calculation assumes the payment processor has not sent a partial authorization,
            # thus we use the amounts stored in the database rather than those received from the payment processor.
            order_total = OrderTotalCalculator().calculate(basket, shipping_charge)
            billing_address = self.payment_processor.get_billing_address(request.data)

            self.handle_order_placement(
                basket.order_number,
                basket.owner,
                basket,
                None,
                shipping_method,
                shipping_charge,
                billing_address,
                order_total
            )
        except:  # pylint: disable=bare-except
            logger.exception(self.order_placement_failure_msg, basket.id)

        return Response({'authorized': True})


class PaymentProcessorNotificationView(APIView):
    """Handle notification from payment processors"""

    # Disable atomicity for the view. Otherwise, we'd be unable to commit to the database
    # until the request had concluded; Django will refuse to commit when an atomic() block
    # is active, since that would break atomicity. Without an order present in the database
    # at the time fulfillment is attempted, asynchronous order fulfillment tasks will fail.
    @method_decorator(transaction.non_atomic_requests)
    def dispatch(self, request, *args, **kwargs):
        return super(PaymentProcessorNotificationView, self).dispatch(request, *args, **kwargs)

    def post(self, request):
        notification_data = request.data
        payment_processor = self._get_processor_for_notification(request.site, notification_data)
        if not payment_processor:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        try:
            if waffle.switch_is_active('async_payment_processor_response_handler'):
                process_notification.delay(
                    payment_processor.NAME,
                    notification_data,
                    site_code=request.site.siteconfiguration.partner.short_code
                )
            else:
                payment_processor.process_notification(notification_data)
        except:  # pylint: disable=bare-except
            logger.exception('Failed to accept [%s] payment processor notification')
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(payment_processor.ACCEPTED_NOTIFICATION_RESPONSE)

    @detail_route(methods=['put', 'patch'])
    def process(self, request):
        notification_data = request.data
        payment_processor_name = notification_data['payment_processor']
        payment_processor = request.site.siteconfiguration.get_payment_processors().get(payment_processor_name)
        if not payment_processor:
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            payment_processor.handle_processor_notification(notification_data)
        except:  # pylint: disable=bare-except
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response()

    def _get_processor_for_notification(self, site, notification_data):
        payment_processors = site.siteconfiguration.get_payment_processors()
        for processor in payment_processors:
            if processor.can_handle_notification(notification_data):
                return processor

        logger.error(
            'Received payment processor notification [%s] which could not be handled '
            'by the processors %s enabled for site [%s].',
            notification_data,
            [processor_name for processor_name, processor in payment_processors],
            site.domain,

        )
        return None


class PaymentProcessorListView(generics.ListAPIView):
    """List the available payment processors"""
    pagination_class = None
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.PaymentProcessorSerializer

    @cache_response(
        PAYMENT_PROCESSOR_CACHE_TIMEOUT,
        key_func=lambda *args, **kwargs: PAYMENT_PROCESSOR_CACHE_KEY,
        cache_errors=False,
    )
    def get(self, request):
        return super(PaymentProcessorListView, self).get(request)

    def get_queryset(self):
        """Fetch the list of payment processor classes based on Django settings."""
        return [processor for __, processor in self.request.site.siteconfiguration.get_payment_processors().items()]
