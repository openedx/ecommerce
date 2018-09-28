from mock import patch
from oscar.test.factories import UserFactory

from ecommerce.core.models import SegmentClient
from ecommerce.extensions.analytics.utils import ECOM_TRACKING_ID_FMT
from ecommerce.extensions.refund.api import create_refunds
from ecommerce.extensions.refund.tests.mixins import RefundTestMixin
from ecommerce.tests.testcases import TestCase


@patch.object(SegmentClient, 'track')
class RefundTrackingTests(RefundTestMixin, TestCase):
    """Tests verifying the behavior of refund tracking."""

    def setUp(self):
        super(RefundTrackingTests, self).setUp()
        self.user = UserFactory()
        self.refund = create_refunds([self.create_order()], self.course.id)[0]

    def assert_refund_event_fired(self, mock_track, refund, tracking_context=None):
        tracking_context = tracking_context or {}
        (event_user_id, event_name, event_payload), kwargs = mock_track.call_args

        self.assertTrue(mock_track.called)
        self.assertEqual(
            event_user_id,
            tracking_context.get('lms_user_id', ECOM_TRACKING_ID_FMT.format(refund.user.id))
        )
        self.assertEqual(event_name, 'Order Refunded')

        expected_context = {
            'ip': tracking_context.get('lms_ip'),
            'Google Analytics': {
                'clientId': tracking_context.get('ga_client_id')
            }
        }
        self.assertEqual(kwargs['context'], expected_context)

        self.assertEqual(event_payload['orderId'], refund.order.number)

        expected_products = [
            {
                'id': line.order_line.partner_sku,
                'quantity': line.quantity,
            } for line in refund.lines.all()
        ]
        self.assertEqual(event_payload['products'], expected_products)

    def test_successful_refund_tracking(self, mock_track):
        """Verify that a successfully placed refund is tracked when Segment is enabled."""
        tracking_context = {'ga_client_id': 'test-client-id', 'lms_user_id': 'test-user-id', 'lms_ip': '127.0.0.1'}
        self.refund.user.tracking_context = tracking_context
        self.refund.user.save()
        self.approve(self.refund)

        self.assert_refund_event_fired(mock_track, self.refund, tracking_context)

    def test_successful_refund_tracking_without_context(self, mock_track):
        """Verify that a successfully placed refund is tracked, even if no tracking context is available."""
        self.approve(self.refund)
        self.assert_refund_event_fired(mock_track, self.refund)

    def test_successful_refund_no_segment_key(self, mock_track):
        """Verify that a successfully placed refund is not tracked when Segment is disabled."""
        self.site.siteconfiguration.segment_key = None
        self.approve(self.refund)
        self.assertFalse(mock_track.called)

    def test_successful_refund_tracking_segment_error(self, mock_track):
        """Verify that errors during refund tracking are logged."""
        # Approve the refund, forcing an exception to be raised when attempting to emit a corresponding event
        with patch('ecommerce.extensions.analytics.utils.logger.exception') as mock_log_exc:
            mock_track.side_effect = Exception('boom!')
            self.approve(self.refund)

        # Verify that an attempt was made to emit a business intelligence event.
        self.assertTrue(mock_track.called)

        # Verify that an error message was logged.
        self.assertTrue(mock_log_exc.called_with('Failed to emit tracking event upon refund completion.'))
