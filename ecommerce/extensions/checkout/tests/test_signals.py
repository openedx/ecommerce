"""
Tests for the ecommerce.extensions.checkout.mixins module.
"""
from decimal import Decimal

from django.test import TestCase, override_settings
from mock import patch
from oscar.test import factories

from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.tests.mixins import BusinessIntelligenceMixin


@override_settings(SEGMENT_KEY='dummy-key')
@patch('analytics.track')
class EdxOrderPlacementMixinTests(BusinessIntelligenceMixin, TestCase):
    """
    Tests validating generic behaviors of the EdxOrderPlacementMixin.
    """
    ORDER_NUMBER = '321'
    CURRENCY = 'test-currency'
    TOTAL = '9.99'

    def setUp(self):
        # create product for test basket / order
        product_class = factories.ProductClassFactory(name='Seat', requires_shipping=False, track_stock=False)
        product_class.save()
        attr = factories.ProductAttributeFactory(code='course_key', product_class=product_class, type="text")
        attr.save()
        parent_product = factories.ProductFactory(
            upc='dummy-parent-product',
            title='dummy-title',
            product_class=product_class,
            structure='parent',
        )
        child_product = factories.ProductFactory(
            upc='dummy-child-product',
            title='test-product-title',
            structure='child',
            parent=parent_product,
        )
        child_product.attr.course_key = 'test-course-key'
        child_product.save()

        # create test user and set up basket / order
        self.user = factories.UserFactory()
        basket = factories.BasketFactory(total_incl_tax=Decimal('10.01'), total_excl_tax=Decimal(self.TOTAL))
        basket.add_product(child_product)
        self.order = factories.create_order(
            user=self.user,
            basket=basket,
            currency=self.CURRENCY,
            number=self.ORDER_NUMBER
        )

    def test_handle_successful_order(self, mock_track):
        """
        Ensure that tracking events are fired with correct content when order
        placement event handling is invoked.
        """
        tracking_context = {'lms_user_id': 'test-user-id', 'lms_client_id': 'test-client-id'}
        self.user.tracking_context = tracking_context
        self.user.save()
        EdxOrderPlacementMixin().handle_successful_order(self.order)
        # ensure event is being tracked
        self.assertTrue(mock_track.called)
        # ensure event data is correct
        self.assert_correct_event(
            mock_track,
            self.order,
            tracking_context['lms_user_id'],
            tracking_context['lms_client_id'],
            self.ORDER_NUMBER,
            self.CURRENCY,
            self.TOTAL
        )

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
            self.ORDER_NUMBER,
            self.CURRENCY,
            self.TOTAL
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
