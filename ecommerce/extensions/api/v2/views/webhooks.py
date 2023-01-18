"""HTTP endpoints for interacting with webhooks."""


import json
import logging

import stripe
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class StripeWebhooksView(APIView):
    """
    Endpoint for Stripe webhook events. A 200 response should be returned as soon as possible
    since Stripe will retry the event if no response is received.

    Django's default cross-site request forgery (CSRF) protection is disabled,
    request are verified instead by the presence of request headers STRIPE_SIGNATURE.
    This endpoint is a public endpoint however it should be used for Stripe servers only.
    """
    http_method_names = ['post']  # accept POST request only
    authentication_classes = []
    permission_classes = [AllowAny]

    stripe.api_key = settings.ECOMMERCE_PAYMENT_PROCESSOR_CONFIG['edx']['stripe']['secret_key']

    @csrf_exempt
    def post(self, request):
        event = None
        payload = request.body

        # TODO REV-3238: secure webhooks with endpoint_secret and stripe signature header
        # Note: this should be done before adding any logic to this endpoint besides logs.

        try:
            event = stripe.Event.construct_from(json.loads(payload), stripe.api_key)
        except ValueError as e:
            logger.exception('StripeWebhooksView failed with %s', e)
            return Response('Invalid payload', status=400)

        # TODO REV-3296: save webhooks event data in webhooks data model. Possibly move the handling of the event
        # to another function, and return response asap if we're listening to many events.

        # Handle the event
        payment_intent = event.data.object
        if event.type == 'payment_intent.succeeded':
            logger.info(
                '[Stripe webhooks] event payment_intent.succeeded with amount %d and payment intent ID [%s].',
                payment_intent.amount,
                payment_intent.id,
            )
            # TODO: define and call a method to handle the successful payment intent.
            # handle_payment_intent_succeeded(payment_intent)
        elif event.type == 'charge.succeeded':
            logger.info(
                '[Stripe webhooks] event charge.succeeded with amount %d and payment intent ID [%s].',
                payment_intent.amount,
                payment_intent.id,
            )
        elif event.type == 'payment_intent.created':
            logger.info(
                '[Stripe webhooks] event payment_intent.created with amount %d and payment intent ID [%s].',
                payment_intent.amount,
                payment_intent.id,
            )
        else:
            logger.warning('[Stripe webhooks] unhandled event with type [%s].', event.type)

        return Response(status=status.HTTP_200_OK)
