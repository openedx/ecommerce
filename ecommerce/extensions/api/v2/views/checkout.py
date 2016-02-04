from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponseBadRequest
from oscar.core.loading import get_class
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ecommerce.extensions.payment.helpers import get_processor_class_by_name
from ecommerce.extensions.api.serializers import CheckoutSerializer

Applicator = get_class('offer.utils', 'Applicator')


class CheckoutView(APIView):
    """
    Prepares a basket for checkout and returns information necessary for the browser to redirect the client
    to the payment process.
    """
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        basket_id = request.data['basket_id']
        payment_processor = request.data['payment_processor']

        # Get the basket, and make sure it belongs to the current user.
        try:
            basket = request.user.baskets.get(id=basket_id)
        except ObjectDoesNotExist:
            return HttpResponseBadRequest('Basket [{}] not found'.format(basket_id))

        # Freeze the basket so that it cannot be modified
        basket.strategy = request.strategy
        Applicator().apply(basket, request.user, request)
        basket.save()

        basket.freeze()

        # Return the payment info
        payment_processor = get_processor_class_by_name(payment_processor)()
        parameters = payment_processor.get_transaction_parameters(basket, request=request)
        payment_page_url = parameters.pop('payment_page_url')

        data = {
            'payment_form_data': parameters,
            'payment_page_url': payment_page_url,
            'payment_processor': payment_processor.NAME,
        }

        serializer = CheckoutSerializer(data)
        return Response(serializer.data)
