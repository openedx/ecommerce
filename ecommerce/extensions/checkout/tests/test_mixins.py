"""
Tests for the ecommerce.extensions.checkout.mixins module.
"""
from decimal import Decimal

from django.test import TestCase, override_settings
from mock import patch
from oscar.core.prices import Price
from oscar.test import factories

from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin


@override_settings(SEGMENT_KEY='dummy-key')
@patch('analytics.track')
@patch('ecommerce.extensions.checkout.mixins.OrderPlacementMixin.handle_order_placement')
class EdxOrderPlacementMixinTests(TestCase):
    """
    Tests validating generic behaviors of the EdxOrderPlacementMixin.
    """

    def setUp(self):
        self.user = factories.UserFactory()
        self.order = factories.create_order(
            currency='test-currency',
            number='321',
            total=Price(currency='dummy-currency', incl_tax=Decimal('10.01'), excl_tax=Decimal('9.99')),
        )

    def call_handle_order_placement(self, tracking_context):
        """ DRY helper. """
        EdxOrderPlacementMixin().handle_order_placement(
            order_number='dummy-order-number',
            user=self.user,
            basket='dummy-basket',
            shipping_address='dummy-shipping-address',
            shipping_method='dummy-shipping-method',
            shipping_charge='dummy-shipping-charge',
            billing_address='dummy-billing-address',
            order_total='dummy-order-total',
            tracking_context=tracking_context
        )

    def assert_correct_event(self, mock_track, order, expected_user_id, expected_client_id):
        """
        Check that the tracking context was correctly reflected in the fired event
        """
        (event_user_id, event_name, event_payload), kwargs = mock_track.call_args
        self.assertEqual(event_user_id, expected_user_id)
        self.assertEqual(event_name, 'Completed Order')
        self.assertEqual(kwargs['context'], {'Google Analytics': {'clientId': expected_client_id}})
        self.assert_correct_event_payload(order, event_payload)

    def assert_correct_event_payload(self, order, actual_event_payload):
        """
        Check that field values in the event payload correctly represent the completed order.
        """
        self.assertEqual(['currency', 'orderId', 'products', 'total'], sorted(actual_event_payload.keys()))
        self.assertEqual(actual_event_payload['currency'], 'test-currency')
        self.assertEqual(actual_event_payload['orderId'], '321')
        self.assertEqual(actual_event_payload['total'], '9.99')

        lines = order.lines.all()
        self.assertEqual(len(lines), len(actual_event_payload['products']))

        # id, sku, name, price, qty, category
        actual_products_dict = {product['sku']: product for product in actual_event_payload['products']}
        for line in lines:
            actual_product = actual_products_dict.get(line.partner_sku)
            self.assertIsNotNone(actual_product)
            self.assertEqual(line.partner_name, actual_product['name'])
            self.assertEqual(str(line.line_price_excl_tax), actual_product['price'])
            self.assertEqual(line.quantity, actual_product['quantity'])
            self.assertEqual(line.category, actual_product['category'])

    def test_handle_order_placement(self, mock_super_handle_order_placement, mock_track):
        """
        Ensure that tracking events are fired with correct content when order
        placement event handling is invoked.
        """
        tracking_context = {'lms_user_id': 'test-user-id', 'lms_client_id': 'test-client-id'}
        mock_super_handle_order_placement.return_value = self.order
        self.call_handle_order_placement(tracking_context)

        # ensure base behavior is getting invoked
        self.assertTrue(mock_super_handle_order_placement.called)
        # ensure event is being tracked
        self.assertTrue(mock_track.called)
        # ensure event data is correct
        self.assert_correct_event(
            mock_track, self.order, tracking_context['lms_user_id'], tracking_context['lms_client_id']
        )

    def test_handle_order_placement_no_context(self, mock_super_handle_order_placement, mock_track):
        """
        Ensure that expected values are substituted when no tracking_context was available.
        """
        tracking_context = {}
        mock_super_handle_order_placement.return_value = self.order
        self.call_handle_order_placement(tracking_context)

        # ensure base behavior is getting invoked
        self.assertTrue(mock_super_handle_order_placement.called)
        # ensure event is being tracked
        self.assertTrue(mock_track.called)
        # ensure event data is correct
        self.assert_correct_event(mock_track, self.order, 'ecommerce-{}'.format(self.user.id), None)

    def test_handle_order_placement_failure(self, mock_super_handle_order_placement, mock_track):
        """
        Ensure that tracking events do not fire when underlying order placement fails.
        """
        tracking_context = {}
        mock_super_handle_order_placement.side_effect = Exception("kaboom!")
        with self.assertRaises(Exception):
            self.call_handle_order_placement(tracking_context)

        # ensure base behavior is getting invoked
        self.assertTrue(mock_super_handle_order_placement.called)
        # ensure no event was fired
        self.assertFalse(mock_track.called)

    @override_settings(SEGMENT_KEY=None)
    def test_handle_order_placement_no_segment_key(self, mock_super_handle_order_placement, mock_track):
        """
        Ensure that tracking events do not fire when there is no segment key configured.
        """
        mock_super_handle_order_placement.return_value = self.order
        self.call_handle_order_placement({})

        # ensure base behavior is getting invoked
        self.assertTrue(mock_super_handle_order_placement.called)
        # ensure no event was fired
        self.assertFalse(mock_track.called)

    def test_handle_order_placement_segment_error(self, mock_super_handle_order_placement, mock_track):
        """
        Ensure that tracking events do not fire when there is no segment key configured.
        """
        with patch('ecommerce.extensions.checkout.mixins.logger.warning') as mock_warning:
            mock_super_handle_order_placement.return_value = self.order
            mock_track.side_effect = Exception("blammo!")
            self.call_handle_order_placement({})

        # ensure base behavior is getting invoked
        self.assertTrue(mock_super_handle_order_placement.called)
        # ensure that analytics.track was called, but the exception was caught
        self.assertTrue(mock_track.called)
        # ensure we logged a warning.
        self.assertTrue(mock_warning.called_with("Unable to emit tracking event upon order placement, skipping."))
