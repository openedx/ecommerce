

import logging

import ddt
from django.test import Client
from django.urls import reverse
from testfixtures import LogCapture

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

    def _build_event_data(self, **kwargs):
        event_type = kwargs.get('event_type', None)
        amount = kwargs.get('amount', None)
        event_id = kwargs.get('event_id', None)
        return {
            'id': 'evt_123dummy',
            'object': 'event',
            'api_version': '2022-08-01',
            'created': 1673630016,
            'data': {
                'object': {
                    'object': 'charge',
                    'id': event_id,
                    'amount': amount,
                    'currency': 'usd',
                    'last_payment_error': None,
                    'metadata': {},
                    'next_action': None,
                },
            },
            'type': event_type,
        }

    @ddt.data('get', 'put', 'patch', 'head')
    def test_method_not_allowed(self, http_method):
        """
        Verify the view only accepts POST HTTP method.
        """
        response = getattr(self.client, http_method)(self.url)
        self.assertEqual(response.status_code, 405)

    @ddt.data(
        ('charge.succeeded', 199, 'ch_123dummy'),
        ('payment_intent.succeeded', 299, 'pi_123dummy'),
    )
    @ddt.unpack
    def test_handled_webhook_event(self, event_type, amount, event_id):
        """
        Verify the expected logs for the known handled event types are logged
        with the correct event type and other attributes.
        """
        post_data = self._build_event_data(event_type=event_type, amount=amount, event_id=event_id)
        expected_logs = [
            (
                log_name,
                'INFO',
                '[Stripe webhooks] event {} with amount {} and payment intent ID [{}].'
                .format(event_type, amount, event_id),
            ),
        ]
        with LogCapture(log_name) as log_capture:
            response = self.client.post(self.url, post_data, content_type='application/json')
            self.assertEqual(response.status_code, 200)
            log_capture.check_present(*expected_logs)

    def test_unhandled_webhook_event(self):
        """
        Verify the expected logs for the unhandled event types are logged with the correct event type.
        """
        post_data = self._build_event_data(event_type='account_updated')
        expected_logs = [
            (
                log_name,
                'INFO',
                '[Stripe webhooks] unhandled event with type [{}].'.format(post_data['type']),
            ),
        ]
        with LogCapture(log_name) as log_capture:
            response = self.client.post(self.url, post_data, content_type='application/json')
            self.assertEqual(response.status_code, 200)
            log_capture.check_present(*expected_logs)
