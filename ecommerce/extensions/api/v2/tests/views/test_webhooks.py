

import logging

import ddt
import mock
from django.test import Client
from django.urls import reverse
from stripe.error import SignatureVerificationError
from testfixtures import LogCapture

from ecommerce.extensions.api.v2.tests.views import JSON_CONTENT_TYPE
from ecommerce.tests.testcases import TestCase

log = logging.getLogger(__name__)
log_name = 'ecommerce.extensions.api.v2.views.webhooks'


@ddt.ddt
class StripeWebhooksViewTests(TestCase):
    """ Tests StripeWebhooksView """

    def setUp(self):
        super(StripeWebhooksViewTests, self).setUp()
        self.url = reverse("api:v2:webhooks:webhook_events")
        self.client = Client(enforce_csrf_checks=True)
        self.mock_settings = {
            'PAYMENT_PROCESSOR_CONFIG': {
                'edx': {
                    'stripe': {
                        'secret_key': 'sk_test_123',
                        'webhook_endpoint_secret': 'whsec_123',
                    }
                }
            },
        }
        self.mock_header = {
            'HTTP_STRIPE_SIGNATURE': 't=1674755157,v1=a5e6655d0f41076ca300150ed98b125ab0203f8672ced6f7cc9c8856517727e8',
        }

    def _build_event_data(self, **kwargs):
        event_type = kwargs.get('event_type', None)
        amount = kwargs.get('amount', None)
        payment_intent_id = kwargs.get('payment_intent_id', None)
        is_dynamic_payment_methods = kwargs.get('is_dynamic_payment_methods', None)

        payment_method_details = {
            'card': {
                'brand': 'visa',
                'country': 'US',
                'exp_month': 4,
                'exp_year': 2025,
                'funding': 'credit',
                'last4': '4242',
            },
            'type': 'card'
        }

        payment_method_details_dpm = {
            'affirm': {
                'order_id': 'JCkYW6Afa0hELU0p1Urf',
            },
            'type': 'affirm'
        }

        charge_data = {
            "id": "ch_3P4QCyH4caH7G0X10RkSR7Px",
            "object": "charge",
            "amount": amount,
            "payment_intent": payment_intent_id,
            "payment_method": "pm_1P4QCvH4caH7G0X1xMAs7Gld",
            "payment_method_details": (
                payment_method_details_dpm if is_dynamic_payment_methods
                else payment_method_details
            ),
        }

        return {
            "id": "evt_3P4Q10H4caH7G0X10U4oCAXb",
            "object": "event",
            "api_version": "2022-08-01",
            "created": 1712851098,
            "data": {
                "object": {
                    "id": payment_intent_id,
                    "object": "payment_intent",
                    "amount": amount,
                    "charges": {
                        "object": "list",
                        "data": [
                            charge_data if event_type == 'payment_intent.succeeded' else None
                        ],
                    },
                    "created": 1712851098,
                    "currency": "usd",
                    "description": "EDX-100001",
                    "metadata": {
                        "order_number": "EDX-100001"
                    },
                    "payment_method": "pm_123dummy",
                    "status": "requires_payment_method",
                }
            },
            "type": event_type
        }

    @ddt.data('get', 'put', 'patch', 'head')
    def test_method_not_allowed(self, http_method):
        """
        Verify the view only accepts POST HTTP method.
        """
        response = getattr(self.client, http_method)(self.url)
        self.assertEqual(response.status_code, 405)

    def test_stripe_event_value_error(self):
        """
        Verify an exception is raised if there is an issue with the Stripe Event from unexpected payload.
        """
        with mock.patch('ecommerce.extensions.api.v2.views.webhooks.logger.exception') as mock_logger:
            with self.settings(**self.mock_settings):
                response = self.client.post(
                    self.url, 'not-expected-data', content_type=JSON_CONTENT_TYPE, **self.mock_header
                )
                self.assertEqual(response.status_code, 400)
                self.assertTrue(mock_logger.called)

    @mock.patch('stripe.Webhook.construct_event')
    def test_stripe_signature_verification_error(self, mock_construct_event):
        """
        Verify an exception is raised if there is any issue with verifying the stripe header/endpoint secret.
        """
        with mock.patch('ecommerce.extensions.api.v2.views.webhooks.logger.exception') as mock_logger:
            with self.settings(**self.mock_settings):
                mock_construct_event.side_effect = SignatureVerificationError(
                    'error on signature verification', self.mock_header['HTTP_STRIPE_SIGNATURE']
                )
                response = self.client.post(
                    self.url, self._build_event_data(), content_type=JSON_CONTENT_TYPE, **self.mock_header
                )
                self.assertEqual(response.status_code, 400)
                self.assertTrue(mock_logger.called)

    @mock.patch('ecommerce.extensions.payment.processors.webhooks.StripeWebhooksProcessor.handle_webhooks_payment')
    @mock.patch('stripe.Webhook.construct_event')
    @ddt.data(
        ('payment_intent.succeeded', 299, 'pi_123dummy', False),
        ('payment_intent.requires_action', 399, 'pi_456dummy', False),
        ('payment_intent.payment_failed', 499, 'pi_789dummy', False),
        ('payment_intent.succeeded', 199, 'pi_123dpm', True),
    )
    @ddt.unpack
    def test_handled_webhook_event(
        self,
        event_type,
        amount,
        payment_intent_id,
        is_dynamic_payment_methods,
        mock_construct_event,
        mock_webhooks_processor
    ):
        """
        Verify the expected logs for the known handled event types are logged
        with the correct event type and other attributes.
        """
        event_data = self._build_event_data(
            event_type=event_type,
            amount=amount,
            payment_intent_id=payment_intent_id,
            is_dynamic_payment_methods=is_dynamic_payment_methods
        )
        expected_logs = [
            (
                log_name,
                'INFO',
                '[Stripe webhooks] event {} with amount {} and payment intent ID [{}].'
                .format(event_type, amount, payment_intent_id),
            ),
        ]
        expected_logs_dpm = [
            (
                log_name,
                'INFO',
                '[Stripe webhooks] Dynamic Payment Methods event {} with amount {} and payment intent ID [{}].'
                .format(event_type, amount, payment_intent_id),
            ),
        ]
        with self.settings(**self.mock_settings):
            mock_construct_event.return_value = event_data
            with LogCapture(log_name) as log_capture:
                response = self.client.post(self.url, event_data, content_type=JSON_CONTENT_TYPE, **self.mock_header)
                self.assertEqual(response.status_code, 200)
                if is_dynamic_payment_methods:
                    mock_webhooks_processor.assert_called()
                    log_capture.check_present(*expected_logs_dpm)
                else:
                    mock_webhooks_processor.assert_not_called()
                    log_capture.check_present(*expected_logs)

    @mock.patch('stripe.Webhook.construct_event')
    def test_unhandled_webhook_event(self, mock_construct_event):
        """
        Verify the expected logs for the unhandled event types are logged with the correct event type.
        """
        event_type = 'account_updated'
        event_data = self._build_event_data(event_type=event_type)
        expected_logs = [
            (
                log_name,
                'WARNING',
                '[Stripe webhooks] unhandled event with type [{}].'.format(event_data['type']),
            ),
        ]
        with self.settings(**self.mock_settings):
            mock_construct_event.return_value = event_data
            with LogCapture(log_name) as log_capture:
                response = self.client.post(self.url, event_data, content_type=JSON_CONTENT_TYPE, **self.mock_header)
                self.assertEqual(response.status_code, 200)
                log_capture.check_present(*expected_logs)
