import logging

from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponseBadRequest
from oscar.core.loading import get_class
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ecommerce.extensions.api.serializers import CheckoutSerializer
from ecommerce.extensions.payment.exceptions import ProcessorNotFoundError

Applicator = get_class('offer.utils', 'Applicator')
logger = logging.getLogger(__name__)


class CheckoutView(APIView):
    """
    Freezes a basket, and returns the information necessary to start the payment process.
    """
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        basket_id = request.data['basket_id']
        payment_processor_name = request.data['payment_processor']

        # Get the basket, and make sure it belongs to the current user.
        try:
            basket = request.user.baskets.get(id=basket_id)
        except ObjectDoesNotExist:
            return HttpResponseBadRequest('Basket [{}] not found.'.format(basket_id))

        # Freeze the basket so that it cannot be modified
        basket.strategy = request.strategy
        Applicator().apply(basket, request.user, request)
        basket.freeze()

        # Return the payment info
        try:
            payment_processor = request.site.siteconfiguration.get_payment_processor_by_name(payment_processor_name)
        except ProcessorNotFoundError:
            logger.exception('Failed to get payment processor [%s].', payment_processor_name)
            return HttpResponseBadRequest(
                'Payment processor [{}] not found.'.format(payment_processor_name)
            )

        parameters = payment_processor.get_transaction_parameters(basket, request=request)
        payment_page_url = parameters.pop('payment_page_url')

        data = {
            'payment_form_data': parameters,
            'payment_page_url': payment_page_url,
            'payment_processor': payment_processor.NAME,
        }

        serializer = CheckoutSerializer(data)
        return Response(serializer.data)
