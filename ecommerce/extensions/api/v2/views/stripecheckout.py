

import logging
import stripe

from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponseBadRequest
from oscar.core.loading import get_class
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ecommerce.extensions.api.serializers import CheckoutSerializer
from ecommerce.extensions.payment.exceptions import ProcessorNotFoundError
from ecommerce.extensions.payment.helpers import get_processor_class_by_name

from ecommerce.extensions.basket.views import BasketAddItemsView

Applicator = get_class('offer.applicator', 'Applicator')
logger = logging.getLogger(__name__)

# Set your secret key. Remember to switch to your live secret key in production!
# See your keys here: https://dashboard.stripe.com/account/apikeys
stripe.api_key = 'sk_test_51HPALSI4kCTHgejljk0osx7grTZxQiktpe21VT9O0KKMKgWsXp0ryENYieyJOlYOqmYV6fMRxnimavl71IjSwYR10083p7dskF'


class CreateCheckoutSession(APIView):
    """
    Freezes a basket, and returns the information necessary to start the payment process.
    """


    def get(self, request):
        return Response(emma='hello world')

    def post(self, request):
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
            'price_data': {
                'currency': 'usd',
                'product_data': {
                'name': 'T-shirt',
                },
                'unit_amount': 2000,
            },
            'quantity': 1,
            }],
            mode='payment',
            success_url='https://example.com/success',
            cancel_url='https://example.com/cancel',
        )
        logger.info('Emma was in this post method')
        response = Response(data={'id':session.id})
        response['Access-Control-Allow-Origin'] = '*'
        return response
