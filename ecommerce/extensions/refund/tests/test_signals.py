

from mock import patch

from ecommerce.core.constants import SEAT_PRODUCT_CLASS_NAME
from ecommerce.core.models import SegmentClient
from ecommerce.extensions.analytics.utils import ECOM_TRACKING_ID_FMT
from ecommerce.extensions.refund.api import create_refunds
from ecommerce.extensions.refund.tests.mixins import RefundTestMixin
from ecommerce.tests.factories import UserFactory
from ecommerce.tests.testcases import TransactionTestCase


@patch.object(SegmentClient, 'track')
class RefundTrackingTests(RefundTestMixin, TransactionTestCase):
    """Tests verifying the behavior of refund tracking."""

    def setUp(self):
        super(RefundTrackingTests, self).setUp()
        self.user = UserFactory(lms_user_id=6179)
        self.refund = create_refunds([self.create_order()], self.course.id)[0]

    def assert_refund_event_fired(self, mock_track, refund, tracking_context=None, expected_user_id=None):
        (event_user_id, event_name, event_payload), kwargs = mock_track.call_args

        self.assertTrue(mock_track.called)
        self.assertEqual(event_name, 'Order Refunded')

        if tracking_context is not None:
            expected_context = {
                'ip': tracking_context['lms_ip'],
                'Google Analytics': {
                    'clientId': tracking_context['ga_client_id']
                },
                'page': {
                    'url': 'https://testserver.fake/'
                },
            }
        else:
            expected_context = {
                'ip': None,
                'Google Analytics': {'clientId': None},
                'page': {'url': 'https://testserver.fake/'}
            }

        if expected_user_id is None:
            expected_user_id = refund.user.lms_user_id

        self.assertEqual(event_user_id, expected_user_id)
        self.assertEqual(kwargs['context'], expected_context)
        self.assertEqual(event_payload['orderId'], refund.order.number)

        expected_products = [
            {
                'id': line.order_line.partner_sku,
                'quantity': line.quantity,
            } for line in refund.lines.all()
        ]

        total = refund.total_credit_excl_tax
        first_product = refund.lines.first().order_line.product
        product_class = first_product.get_product_class().name
        if product_class == SEAT_PRODUCT_CLASS_NAME:
            title = first_product.course.name
        else:
            title = first_product.title
        self.assertEqual(event_payload['products'], expected_products)
        self.assertEqual(event_payload['total'], total)
        self.assertEqual(event_payload['title'], title)

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

    def test_refund_tracking_without_lms_user_id(self, mock_track):
        """Verify that a successfully placed refund is tracked, even if no LMS user id is available."""
        self.refund.user.lms_user_id = None
        self.approve(self.refund)
        expected_user_id = ECOM_TRACKING_ID_FMT.format(self.refund.user.id)
        self.assert_refund_event_fired(mock_track, self.refund, expected_user_id=expected_user_id)

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
        mock_log_exc.assert_called_with('Failed to emit tracking event upon refund completion.')
