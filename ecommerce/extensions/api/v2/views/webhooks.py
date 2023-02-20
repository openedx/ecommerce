"""HTTP endpoints for interacting with webhooks."""


import logging

import stripe
from django.conf import settings
from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from oscar.apps.partner import strategy
from oscar.core.loading import get_class, get_model
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from stripe.error import SignatureVerificationError

from ecommerce.extensions.analytics.utils import track_segment_event
from ecommerce.extensions.basket.constants import PAYMENT_INTENT_ID_ATTRIBUTE
from ecommerce.extensions.basket.utils import basket_add_organization_attribute
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.payment.constants import STRIPE_CARD_TYPE_MAP
from ecommerce.extensions.payment.processors import HandledProcessorResponse
from ecommerce.extensions.payment.processors.stripe import Stripe

logger = logging.getLogger(__name__)

stripe.api_key = settings.PAYMENT_PROCESSOR_CONFIG['edx']['stripe']['secret_key']
endpoint_secret = settings.PAYMENT_PROCESSOR_CONFIG['edx']['stripe']['webhook_endpoint_secret']

Applicator = get_class('offer.applicator', 'Applicator')
Basket = get_model('basket', 'Basket')
BasketAttribute = get_model('basket', 'BasketAttribute')
BasketAttributeType = get_model('basket', 'BasketAttributeType')


class StripeWebhooksView(APIView, EdxOrderPlacementMixin):
    """
    Endpoint for Stripe webhook events. A 200 response should be returned as soon as possible
    since Stripe will retry the event if no response is received.

    Django's default cross-site request forgery (CSRF) protection is disabled,
    request are verified instead by the presence of request headers STRIPE_SIGNATURE.
    This endpoint is a public endpoint however it should be used for Stripe servers only.
    """
    NAME = 'stripe'
    http_method_names = ['post']  # accept POST request only
    authentication_classes = []
    permission_classes = [AllowAny]

    @csrf_exempt
    def post(self, request):
        payload = request.body
        sig_header = request.META['HTTP_STRIPE_SIGNATURE']
        event = None

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, endpoint_secret
            )
        except ValueError as e:
            logger.exception('StripeWebhooksView failed with %s', e)
            return Response('Invalid payload', status=400)
        except SignatureVerificationError as e:
            logger.exception('StripeWebhooksView SignatureVerificationError: %s', e)
            return Response('Invalid signature', status=400)

        # TODO REV-3296: save webhooks event data in webhooks data model. Possibly move the handling of the event
        # to another function, and return response asap if we're listening to many events.

        # Handle the event
        payment_intent = event.data.object
        if event.type == 'payment_intent.succeeded':
            # TODO: idempotency check order
            logger.info(
                '[Stripe webhooks] event payment_intent.succeeded with amount %d and payment intent ID [%s].',
                payment_intent.amount,
                payment_intent.id,
            )
            self.handle_payment_intent_succeeded(payment_intent, request)
        elif event.type == 'payment_intent.payment_failed':
            logger.info(
                '[Stripe webhooks] event payment_intent.payment_failed with amount %d and payment intent ID [%s].',
                payment_intent.amount,
                payment_intent.id,
            )
            # TODO: define and call a method to handle failed payment intent.
        elif event.type == 'payment_intent.requires_action':
            logger.info(
                '[Stripe webhooks] event payment_intent.requires_action with amount %d and payment intent ID [%s].',
                payment_intent.amount,
                payment_intent.id,
            )
            # TODO: define and call a method to handle requires_action for 3DS.
        else:
            logger.warning('[Stripe webhooks] unhandled event with type [%s].', event.type)

        return Response(status=status.HTTP_200_OK)

    def error_page_response(self):
        """Tell the frontend to redirect to a generic error page."""
        return JsonResponse({}, status=400)

    def get_basket(self, payment_intent_id, request):
        """
        Retrieve a basket using a payment intent ID.

        Arguments:
            payment_intent_id: payment_intent_id received from Stripe.

        Returns:
            It will return related basket or log exception and return None if
            duplicate payment_intent_id* received or any other exception occurred.
        """
        try:
            payment_intent_id_attribute, __ = BasketAttributeType.objects.get_or_create(
                name=PAYMENT_INTENT_ID_ATTRIBUTE
            )
            basket_attribute = BasketAttribute.objects.get(
                attribute_type=payment_intent_id_attribute,
                value_text=payment_intent_id,
            )
            basket = basket_attribute.basket
            basket.strategy = strategy.Default()

            Applicator().apply(basket, basket.owner, request)
            logger.info(
                'Applicator applied, basket id: [%s]. Processed by [%s].',
                basket.id, self.NAME)
            basket_add_organization_attribute(basket, request.POST)
        except MultipleObjectsReturned:
            logger.warning(u"Duplicate payment_intent_id [%s] received from Stripe.", payment_intent_id)
            return None
        except ObjectDoesNotExist:
            logger.warning(u"Could not find payment_intent_id [%s] among baskets.", payment_intent_id)
            return None
        except Exception:  # pylint: disable=broad-except
            logger.exception(u"Unexpected error during basket retrieval while executing Stripe payment.")
            return None
        return basket

    def handle_payment_intent_succeeded(self, payment_intent, request):
        basket = self.get_basket(payment_intent.id, request)

        if not basket:
            logger.info(
                'Received Stripe payment notification for non-existent basket with payment intent id [%s].',
                payment_intent.id,
            )
            return redirect(Stripe.error_url)

        Stripe.record_processor_response(
            self,
            response=payment_intent,
            transaction_id=payment_intent.id,
            basket=basket
        )

        logger.info(
            'Successfully confirmed Stripe payment intent [%s] for basket [%d] and order number [%s].',
            payment_intent.id,
            basket.id,
            basket.order_number,
        )

        total = basket.total_incl_tax
        currency = basket.currency
        card_object = payment_intent['charges']['data'][0]['payment_method_details']['card']
        card_number = card_object['last4']
        card_type = STRIPE_CARD_TYPE_MAP.get(card_object['brand'])

        handled_processor_response = HandledProcessorResponse(
            transaction_id=payment_intent.id,
            total=total,
            currency=currency,
            card_number=card_number,
            card_type=card_type
        )

        properties = {
            'basket_id': basket.id,
            'processor_name': self.NAME,
        }
        # We only record successful payments in the database.
        self.record_payment(basket, handled_processor_response)
        properties.update({'total': handled_processor_response.total, 'success': True, })
        track_segment_event(basket.site, basket.owner, 'Payment Processor Response', properties)

        billing_address_obj = Stripe.get_address_from_token(
            payment_intent.id
        )

        try:
            billing_address = Stripe.create_billing_address(
                user=request.user,
                billing_address=billing_address_obj
            )
        except Exception as err:  # pylint: disable=broad-except
            logger.exception('Error creating billing address for basket [%d]: %s', basket.id, err)
            billing_address = None

        try:
            order = self.create_order(request, basket, billing_address)
            self.handle_post_order(order)
        except Exception:  # pylint: disable=broad-except
            logger.exception(
                'Error processing order for transaction [%s], with order [%s] and basket [%d]. Processed by [%s].',
                payment_intent.id,
                basket.order_number,
                basket.id,
                self.NAME,
            )
            return self.error_page_response()

        return self.receipt_page_response(basket, request)
