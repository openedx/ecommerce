"""
Tests for the ecommerce.extensions.checkout.mixins module.
"""
from decimal import Decimal

from django.test import TestCase, override_settings
from mock import Mock, patch
from oscar.test.newfactories import UserFactory
from testfixtures import LogCapture

from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.refund.tests.mixins import RefundTestMixin
from ecommerce.tests.mixins import BusinessIntelligenceMixin


LOGGER_NAME = 'ecommerce.extensions.analytics.utils'


@override_settings(SEGMENT_KEY='dummy-key')
@patch('analytics.track')
class EdxOrderPlacementMixinTests(BusinessIntelligenceMixin, RefundTestMixin, TestCase):
    """
    Tests validating generic behaviors of the EdxOrderPlacementMixin.
    """
    def setUp(self):
        super(EdxOrderPlacementMixinTests, self).setUp()

        self.user = UserFactory()
        self.order = self.create_order()

    def test_handle_payment_logging(self, __):
        """
        Ensure that we emit a log entry upon receipt of a payment notification.
        """
        amount = Decimal('9.99')
        basket_id = 'test-basket-id'
        currency = 'USD'
        processor_name = 'test-processor-name'
        reference = 'test-reference'
        user_id = '1'

        mock_source = Mock(currency=currency)
        mock_payment_event = Mock(
            amount=amount,
            processor_name=processor_name,
            reference=reference
        )
        mock_handle_processor_response = Mock(return_value=(mock_source, mock_payment_event))
        mock_payment_processor = Mock(handle_processor_response=mock_handle_processor_response)

        with patch(
            'ecommerce.extensions.checkout.mixins.EdxOrderPlacementMixin.payment_processor',
            mock_payment_processor
        ):
            mock_basket = Mock(id=basket_id, owner=Mock(id=user_id))
            with LogCapture(LOGGER_NAME) as l:
                EdxOrderPlacementMixin().handle_payment(Mock(), mock_basket)
                l.check(
                    (
                        LOGGER_NAME,
                        'INFO',
                        'payment_received: amount="{}", basket_id="{}", currency="{}", '
                        'processor_name="{}", reference="{}", user_id="{}"'.format(
                            amount,
                            basket_id,
                            currency,
                            processor_name,
                            reference,
                            user_id
                        )
                    )
                )

    def test_handle_successful_order(self, mock_track):
        """
        Ensure that tracking events are fired with correct content when order
        placement event handling is invoked.
        """
        tracking_context = {'lms_user_id': 'test-user-id', 'lms_client_id': 'test-client-id'}
        self.user.tracking_context = tracking_context
        self.user.save()

        with LogCapture(LOGGER_NAME) as l:
            EdxOrderPlacementMixin().handle_successful_order(self.order)
            # ensure event is being tracked
            self.assertTrue(mock_track.called)
            # ensure event data is correct
            self.assert_correct_event(
                mock_track,
                self.order,
                tracking_context['lms_user_id'],
                tracking_context['lms_client_id'],
                self.order.number,
                self.order.currency,
                self.order.total_excl_tax
            )
            l.check(
                (
                    LOGGER_NAME,
                    'INFO',
                    'order_placed: amount="{}", basket_id="{}", currency="{}", order_number="{}", user_id="{}"'.format(
                        self.order.total_excl_tax,
                        self.order.basket.id,
                        self.order.currency,
                        self.order.number,
                        self.order.user.id
                    )
                )
            )

    def test_handle_successful_free_order(self, mock_track):
        """Verify that tracking events are not emitted for free orders."""
        order = self.create_order(free=True)
        EdxOrderPlacementMixin().handle_successful_order(order)

        # Verify that no event was emitted.
        self.assertFalse(mock_track.called)

    def test_handle_successful_order_no_context(self, mock_track):
        """
        Ensure that expected values are substituted when no tracking_context
        was available.
        """
        EdxOrderPlacementMixin().handle_successful_order(self.order)
        # ensure event is being tracked
        self.assertTrue(mock_track.called)
        # ensure event data is correct
        self.assert_correct_event(
            mock_track,
            self.order,
            'ecommerce-{}'.format(self.user.id),
            None,
            self.order.number,
            self.order.currency,
            self.order.total_excl_tax
        )

    @override_settings(SEGMENT_KEY=None)
    def test_handle_successful_order_no_segment_key(self, mock_track):
        """
        Ensure that tracking events do not fire when there is no Segment key
        configured.
        """
        EdxOrderPlacementMixin().handle_successful_order(self.order)
        # ensure no event was fired
        self.assertFalse(mock_track.called)

    def test_handle_successful_order_segment_error(self, mock_track):
        """
        Ensure that exceptions raised while emitting tracking events are
        logged, but do not otherwise interrupt program flow.
        """
        with patch('ecommerce.extensions.analytics.utils.logger.exception') as mock_log_exc:
            mock_track.side_effect = Exception("clunk")
            EdxOrderPlacementMixin().handle_successful_order(self.order)
        # ensure that analytics.track was called, but the exception was caught
        self.assertTrue(mock_track.called)
        # ensure we logged a warning.
        self.assertTrue(mock_log_exc.called_with("Failed to emit tracking event upon order placement."))
