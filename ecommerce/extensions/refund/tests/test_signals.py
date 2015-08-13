from django.test import TestCase, override_settings
from mock import patch
from oscar.test.newfactories import UserFactory

from ecommerce.extensions.refund.api import create_refunds
from ecommerce.extensions.refund.tests.mixins import RefundTestMixin
from ecommerce.tests.mixins import BusinessIntelligenceMixin


@override_settings(SEGMENT_KEY='dummy-key')
@patch('analytics.track')
class RefundTrackingTests(BusinessIntelligenceMixin, RefundTestMixin, TestCase):
    """Tests verifying the behavior of refund tracking."""

    def setUp(self):
        super(RefundTrackingTests, self).setUp()

        self.user = UserFactory()
        self.order = self.create_order()
        self.refund = create_refunds([self.order], self.course.id)[0]

    def test_successful_refund_tracking(self, mock_track):
        """Verify that a successfully placed refund is tracked when Segment is enabled."""
        tracking_context = {'lms_user_id': 'test-user-id', 'lms_client_id': 'test-client-id'}
        self.refund.user.tracking_context = tracking_context
        self.refund.user.save()

        # Approve the refund.
        self.approve(self.refund)

        # Verify that a corresponding business intelligence event was emitted.
        self.assertTrue(mock_track.called)

        # Verify the event's payload.
        self.assert_correct_event(
            mock_track,
            self.refund,
            tracking_context['lms_user_id'],
            tracking_context['lms_client_id'],
            self.order.number,
            self.refund.currency,
            self.refund.total_credit_excl_tax
        )

    def test_successful_zero_dollar_refund_no_tracking(self, mock_track):
        """
        Verify that tracking events are not emitted for refunds corresponding
        to a total credit of 0.
        """
        order = self.create_order(free=True)
        create_refunds([order], self.course.id)

        # Verify that no business intelligence event was emitted. Refunds corresponding
        # to a total credit of 0 are automatically approved upon creation.
        self.assertFalse(mock_track.called)

    def test_successful_refund_tracking_without_context(self, mock_track):
        """Verify that a successfully placed refund is tracked, even if no tracking context is available."""
        # Approve the refund.
        self.approve(self.refund)

        # Verify that a corresponding business intelligence event was emitted.
        self.assertTrue(mock_track.called)

        # Verify the event's payload.
        self.assert_correct_event(
            mock_track,
            self.refund,
            'ecommerce-{}'.format(self.user.id),
            None,
            self.order.number,
            self.refund.currency,
            self.refund.total_credit_excl_tax
        )

    @override_settings(SEGMENT_KEY=None)
    def test_successful_refund_no_segment_key(self, mock_track):
        """Verify that a successfully placed refund is not tracked when Segment is disabled."""
        # Approve the refund.
        self.approve(self.refund)

        # Verify that no business intelligence event was emitted.
        self.assertFalse(mock_track.called)

    def test_successful_refund_tracking_segment_error(self, mock_track):
        """Verify that errors during refund tracking are logged."""
        # Approve the refund, forcing an exception to be raised when attempting to emit a corresponding event
        with patch('ecommerce.extensions.analytics.utils.logger.exception') as mock_log_exc:
            mock_track.side_effect = Exception("boom!")
            self.approve(self.refund)

        # Verify that an attempt was made to emit a business intelligence event.
        self.assertTrue(mock_track.called)

        # Verify that an error message was logged.
        self.assertTrue(mock_log_exc.called_with("Failed to emit tracking event upon refund completion."))
