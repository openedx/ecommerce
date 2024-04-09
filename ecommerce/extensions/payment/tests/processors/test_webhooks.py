

import logging

import mock
from django.test import RequestFactory
from oscar.core.loading import get_class, get_model

from ecommerce.extensions.basket.utils import basket_add_payment_intent_id_attribute
from ecommerce.extensions.payment.processors.webhooks import StripeWebhooksPayment
from ecommerce.extensions.payment.tests.processors.mixins import PaymentProcessorTestCaseMixin
from ecommerce.tests.factories import UserFactory
from ecommerce.tests.testcases import TestCase

log = logging.getLogger(__name__)

BillingAddress = get_model('order', 'BillingAddress')
Country = get_model('address', 'Country')
OrderNumberGenerator = get_class('order.utils', 'OrderNumberGenerator')


class StripeWebhooksPaymentTests(PaymentProcessorTestCaseMixin, TestCase):
    """ Tests StripeWebhooksPayment """
    processor_class = StripeWebhooksPayment
    processor_name = 'stripe'

    def setUp(self):
        super(StripeWebhooksPaymentTests, self).setUp()
        self.site_configuration.client_side_payment_processor = 'stripe'
        self.site_configuration.save()
        Country.objects.create(iso_3166_1_a2='US', name='US')
        self.request = RequestFactory()
        self.request.site = self.site
        self.user = UserFactory()
        self.request.user = self.user

    def _get_order_number_from_basket(self, basket):
        return OrderNumberGenerator().order_number(basket)

    def _build_payment_intent_data(self, basket, payment_intent_status=None):
        return {
            "id": "pi_3OzUOMH4caH7G0X114tkIL0X",
            "object": "payment_intent",
            "status": "succeeded",
            "amount": 14900,
            "charges": {
                "object": "list",
                "data": [{
                    "id": "py_3OzUOMH4caH7G0X11OOKbfIk",
                    "object": "charge",
                    "amount": 14900,
                    "billing_details": {
                        "address": {
                            "city": "Beverly Hills",
                            "country": "US",
                            "line1": "Amsterdam Ave",
                            "line2": "Apt 214",
                            "postal_code": "10024",
                            "state": "NY"
                        },
                        "email": "customer@email.us",
                        "name": "Test Person-us",
                    },
                    "created": 1711676524,
                    "currency": "usd",
                    "description": self._get_order_number_from_basket(basket),
                    "metadata": {
                        "order_number": self._get_order_number_from_basket(basket)
                    },
                    "payment_intent": "pi_3OzUOMH4caH7G0X114tkIL0X",
                    "payment_method": "pm_1OzURzH4caH7G0X19vH5rGBT",
                    "payment_method_details": {
                        "affirm": {
                            "order_id": "JCkYW6Afa0hELU0p1Urf",
                        },
                        "type": "affirm"
                    },
                    "status": payment_intent_status,
                }],
            },
            "client_secret": "pi_3OzUOMH4caH7G0X114tkIL0X_secret_SYz2fcAkT2hIWhpdRTqUwRFHF",
            "confirmation_method": "automatic",
            "created": 1711676282,
            "currency": "usd",
            "description": self._get_order_number_from_basket(basket),
            "payment_method": "pm_1OzURzH4caH7G0X19vH5rGBT",
            "payment_method_configuration_details": {
                "id": "pmc_1LspDWH4caH7G0X1LXrN8QMJ",
            },
            "payment_method_options": {
                "affirm": {
                    "preferred_locale": "en"
                },
                "card": {
                    "request_three_d_secure": "automatic"
                },
            },
            "payment_method_types": [
                "card",
                "affirm"
            ],
            "secret_key_confirmation": "required",
        }

    def test_configuration(self):  # pylint: disable=arguments-differ
        """
        Tests configuration.
        """
        self.skipTest('StripeWebhooksPayment processor does not currently require configuration.')

    def test_name(self):
        """
        Test that the name constant on the processor class is correct.
        """
        self.assertEqual(self.processor.NAME, self.processor_name)

    def test_handle_processor_response(self):
        """
        Tests handle_processor_response.
        """
        self.skipTest('StripeWebhooksPayment processor does not currently implement handle_processor_response.')

    def test_get_transaction_parameters(self):
        """
        Tests transaction parameters.
        """
        self.skipTest('StripeWebhooksPayment processor does not currently implement get_transaction_parameters.')

    def test_issue_credit(self):
        """
        Test issue credit.
        """
        self.assertRaises(NotImplementedError, self.processor_class(self.site).issue_credit, None, None, None, 0, 'USD')

    def test_issue_credit_error(self):
        """
        Tests that Webhooks payments processor does not support issuing credit.
        """
        self.skipTest('Webhooks payments processor does not yet support issuing credit.')

    @mock.patch('ecommerce.extensions.checkout.mixins.EdxOrderPlacementMixin.handle_post_order')
    @mock.patch('stripe.PaymentIntent.retrieve')
    @mock.patch('ecommerce.extensions.payment.processors.webhooks.track_segment_event')
    def test_handle_webhooks_payment(self, mock_track, mock_retrieve, mock_handle_post_order):
        """
        Verify a payment received via Stripe webhooks is processed, an order is created and fulfilled.
        """
        succeeded_payment_intent = self._build_payment_intent_data(self.basket, payment_intent_status='succeeded')

        # Need to associate the Payment Intent to the Basket
        basket_add_payment_intent_id_attribute(self.basket, succeeded_payment_intent['id'])

        mock_retrieve.return_value = {
            'id': succeeded_payment_intent['id'],
            'client_secret': succeeded_payment_intent['client_secret'],
            'payment_method': {
                'id': succeeded_payment_intent['payment_method'],
                'object': 'payment_method',
                'billing_details': succeeded_payment_intent['charges']['data'][0]['billing_details'],
                'type': succeeded_payment_intent['charges']['data'][0]['payment_method_details']['type']
            },
        }
        self.processor_class(self.site).handle_webhooks_payment(
            self.request, succeeded_payment_intent, 'afterpay_clearpay'
        )
        properties = {
            'basket_id': self.basket.id,
            'processor_name': 'stripe',
            'stripe_enabled': True,
            'total': self.basket.total_incl_tax,
            'success': True,
        }
        mock_track.assert_called_once_with(
            self.basket.site, self.basket.owner, 'Payment Processor Response', properties
        )
        mock_handle_post_order.assert_called_once()
