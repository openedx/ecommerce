"""
Tests for the ecommerce.extensions.checkout.mixins module.
"""
import mock
from django.core import mail
from django.test import RequestFactory
from oscar.core.loading import get_class, get_model
from oscar.test.factories import BasketFactory, ProductFactory, UserFactory
from testfixtures import LogCapture
from waffle.models import Sample

from ecommerce.core.constants import ENROLLMENT_CODE_PRODUCT_CLASS_NAME, ENROLLMENT_CODE_SWITCH
from ecommerce.core.models import BusinessClient, SegmentClient
from ecommerce.core.tests import toggle_switch
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.analytics.utils import (
    ECOM_TRACKING_ID_FMT,
    parse_tracking_context,
    translate_basket_line_for_segment
)
from ecommerce.extensions.basket.utils import basket_add_organization_attribute
from ecommerce.extensions.checkout.exceptions import BasketNotFreeError
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.fulfillment.status import ORDER
from ecommerce.extensions.payment.tests.mixins import PaymentEventsMixin
from ecommerce.extensions.payment.tests.processors import DummyProcessor
from ecommerce.extensions.refund.tests.mixins import RefundTestMixin
from ecommerce.extensions.test.factories import create_basket, create_order
from ecommerce.invoice.models import Invoice
from ecommerce.tests.factories import SiteConfigurationFactory
from ecommerce.tests.mixins import BusinessIntelligenceMixin
from ecommerce.tests.testcases import TestCase

LOGGER_NAME = 'ecommerce.extensions.analytics.utils'
Basket = get_model('basket', 'Basket')
NoShippingRequired = get_class('shipping.methods', 'NoShippingRequired')
OrderTotalCalculator = get_class('checkout.calculators', 'OrderTotalCalculator')
PaymentEventType = get_model('order', 'PaymentEventType')
SourceType = get_model('payment', 'SourceType')
Product = get_model('catalogue', 'Product')


@mock.patch.object(SegmentClient, 'track')
class EdxOrderPlacementMixinTests(BusinessIntelligenceMixin, PaymentEventsMixin, RefundTestMixin, TestCase):
    """
    Tests validating generic behaviors of the EdxOrderPlacementMixin.
    """

    def setUp(self):
        super(EdxOrderPlacementMixinTests, self).setUp()
        self.user = UserFactory()
        self.order = self.create_order(status=ORDER.OPEN)

    def test_handle_payment_logging(self, __):
        """
        Ensure that we emit a log entry upon receipt of a payment notification, and create Source and PaymentEvent
        objects.
        """
        basket = create_basket(owner=self.user, site=self.site)

        mixin = EdxOrderPlacementMixin()
        mixin.payment_processor = DummyProcessor(self.site)
        processor_name = DummyProcessor.NAME
        total = basket.total_incl_tax
        reference = basket.id

        with LogCapture(LOGGER_NAME) as l:
            mixin.handle_payment({}, basket)
            l.check(
                (
                    LOGGER_NAME,
                    'INFO',
                    'payment_received: amount="{}", basket_id="{}", currency="{}", '
                    'processor_name="{}", reference="{}", user_id="{}"'.format(
                        total,
                        basket.id,
                        basket.currency,
                        processor_name,
                        reference,
                        self.user.id
                    )
                )
            )

        # pylint: disable=protected-access

        # Validate a payment Source was created
        source_type = SourceType.objects.get(code=processor_name)
        label = self.user.username
        self.assert_basket_matches_source(basket, mixin._payment_sources[-1], source_type, reference, label)

        # Validate the PaymentEvent was created
        paid_type = PaymentEventType.objects.get(code='paid')
        self.assert_valid_payment_event_fields(mixin._payment_events[-1], total, paid_type, processor_name, reference)

    def test_order_number_collision(self, _mock_track):
        """
        Verify that an attempt to create an order with the same number as an existing
        order causes an exception to be raised.
        """
        order_placement_mixin = EdxOrderPlacementMixin()

        basket = self.order.basket

        shipping_method = NoShippingRequired()
        shipping_charge = shipping_method.calculate(basket)

        order_total = OrderTotalCalculator().calculate(basket, shipping_charge)

        with self.assertRaises(ValueError):
            order_placement_mixin.handle_order_placement(
                self.order.number,
                self.user,
                basket,
                None,
                shipping_method,
                shipping_charge,
                None,
                order_total,
            )

    def test_handle_successful_order(self, mock_track):
        """
        Ensure that tracking events are fired with correct content when order
        placement event handling is invoked.
        """
        tracking_context = {'ga_client_id': 'test-client-id', 'lms_user_id': 'test-user-id', 'lms_ip': '127.0.0.1'}
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
                tracking_context['ga_client_id'],
                tracking_context['lms_ip'],
                self.order.number,
                self.order.currency,
                self.order.total_excl_tax
            )
            l.check(
                (
                    LOGGER_NAME,
                    'INFO',
                    'order_placed: amount="{}", basket_id="{}", contains_coupon="{}", currency="{}",'
                    ' order_number="{}", user_id="{}"'.format(
                        self.order.total_excl_tax,
                        self.order.basket.id,
                        self.order.contains_coupon,
                        self.order.currency,
                        self.order.number,
                        self.order.user.id
                    )
                )
            )

    def test_handle_post_order_for_bulk_purchase(self, __):
        """
        Ensure that the bulk purchase order is linked to the provided business
        client when the method `handle_post_order` is invoked.
        """
        toggle_switch(ENROLLMENT_CODE_SWITCH, True)

        course = CourseFactory(partner=self.partner)
        course.create_or_update_seat('verified', True, 50, create_enrollment_code=True)
        enrollment_code = Product.objects.get(product_class__name=ENROLLMENT_CODE_PRODUCT_CLASS_NAME)
        user = UserFactory()
        basket = BasketFactory(owner=user, site=self.site)
        basket.add_product(enrollment_code, quantity=1)
        order = create_order(number=1, basket=basket, user=user)
        request_data = {'organization': 'Dummy Business Client'}
        # Manually add organization attribute on the basket for testing
        basket_add_organization_attribute(basket, request_data)

        EdxOrderPlacementMixin().handle_post_order(order)

        # Now verify that a new business client has been created in current
        # order is now linked with that client through Invoice model.
        business_client = BusinessClient.objects.get(name=request_data['organization'])
        assert Invoice.objects.get(order=order).business_client == business_client

    def test_handle_post_order_for_seat_purchase(self, __):
        """
        Ensure that the single seat purchase order is not linked any business
        client when the method `handle_post_order` is invoked.
        """
        toggle_switch(ENROLLMENT_CODE_SWITCH, False)

        course = CourseFactory(partner=self.partner)
        verified_product = course.create_or_update_seat('verified', True, 50)
        user = UserFactory()
        basket = BasketFactory(owner=user, site=self.site)
        basket.add_product(verified_product, quantity=1)
        order = create_order(number=1, basket=basket, user=user)
        request_data = {'organization': 'Dummy Business Client'}
        # Manually add organization attribute on the basket for testing
        basket_add_organization_attribute(basket, request_data)

        EdxOrderPlacementMixin().handle_post_order(order)

        # Now verify that the single seat order is not linked to business
        # client by checking that there is no record for BusinessClient.
        assert not BusinessClient.objects.all()

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
            ECOM_TRACKING_ID_FMT.format(self.user.id),
            None,
            None,
            self.order.number,
            self.order.currency,
            self.order.total_excl_tax
        )

    def test_handle_successful_order_no_segment_key(self, mock_track):
        """
        Ensure that tracking events do not fire when there is no Segment key
        configured.
        """
        self.site.siteconfiguration.segment_key = None
        EdxOrderPlacementMixin().handle_successful_order(self.order)
        # ensure no event was fired
        self.assertFalse(mock_track.called)

    def test_handle_successful_order_segment_error(self, mock_track):
        """
        Ensure that exceptions raised while emitting tracking events are
        logged, but do not otherwise interrupt program flow.
        """
        with mock.patch('ecommerce.extensions.analytics.utils.logger.exception') as mock_log_exc:
            mock_track.side_effect = Exception("clunk")
            EdxOrderPlacementMixin().handle_successful_order(self.order)
        # ensure that analytics.track was called, but the exception was caught
        self.assertTrue(mock_track.called)
        # ensure we logged a warning.
        self.assertTrue(mock_log_exc.called_with("Failed to emit tracking event upon order placement."))

    def test_handle_successful_async_order(self, __):
        """
        Verify that a Waffle Sample can be used to control async order fulfillment.
        """
        sample, created = Sample.objects.get_or_create(
            name='async_order_fulfillment',
            defaults={
                'percent': 100.0,
                'note': 'Determines what percentage of orders are fulfilled asynchronously.',
            }
        )

        if not created:
            sample.percent = 100.0
            sample.save()

        with mock.patch('ecommerce.extensions.checkout.mixins.fulfill_order.delay') as mock_delay:
            EdxOrderPlacementMixin().handle_successful_order(self.order)
            self.assertTrue(mock_delay.called)
            mock_delay.assert_called_once_with(self.order.number, site_code=self.partner.short_code)

    def test_place_free_order(self, __):
        """ Verify an order is placed and the basket is submitted. """
        basket = create_basket(empty=True)
        basket.add_product(ProductFactory(stockrecords__price_excl_tax=0))
        order = EdxOrderPlacementMixin().place_free_order(basket)

        self.assertIsNotNone(order)
        self.assertEqual(basket.status, Basket.SUBMITTED)

    def test_non_free_basket_order(self, __):
        """ Verify an error is raised for non-free basket. """
        basket = create_basket(empty=True)
        basket.add_product(ProductFactory(stockrecords__price_excl_tax=10))

        with self.assertRaises(BasketNotFreeError):
            EdxOrderPlacementMixin().place_free_order(basket)

    def test_send_confirmation_message(self, __):
        """
        Verify the send confirmation message override functions as expected
        """
        factory = RequestFactory()
        request = factory.get('example.com')
        user = self.create_user()
        user.email = 'test_user@example.com'
        request.user = user
        site_from_email = 'from@example.com'
        site_configuration = SiteConfigurationFactory(partner__name='Tester', from_email=site_from_email)
        request.site = site_configuration.site
        order = create_order()
        order.user = user
        mixin = EdxOrderPlacementMixin()
        mixin.request = request

        # Happy path
        mixin.send_confirmation_message(order, 'ORDER_PLACED', request.site)
        self.assertEqual(mail.outbox[0].from_email, site_from_email)
        mail.outbox = []

        # Invalid code path (graceful exit)
        mixin.send_confirmation_message(order, 'INVALID_CODE', request.site)
        self.assertEqual(len(mail.outbox), 0)

        # Invalid messages container path (graceful exit)
        with mock.patch('ecommerce.extensions.checkout.mixins.CommunicationEventType.objects.get') as mock_get:
            mock_event_type = mock.Mock()
            mock_event_type.get_messages.return_value = {}
            mock_get.return_value = mock_event_type
            mixin.send_confirmation_message(order, 'ORDER_PLACED', request.site)
            self.assertEqual(len(mail.outbox), 0)

            mock_event_type.get_messages.return_value = {'body': None}
            mock_get.return_value = mock_event_type
            mixin.send_confirmation_message(order, 'ORDER_PLACED', request.site)
            self.assertEqual(len(mail.outbox), 0)

    def test_valid_payment_segment_logging(self, mock_track):
        """
        Verify the "Payment Info Entered" Segment event is fired after payment info is validated
        """
        tracking_context = {'ga_client_id': 'test-client-id', 'lms_user_id': 'test-user-id', 'lms_ip': '127.0.0.1'}
        self.user.tracking_context = tracking_context
        self.user.save()

        basket = create_basket(owner=self.user, site=self.site)

        mixin = EdxOrderPlacementMixin()
        mixin.payment_processor = DummyProcessor(self.site)

        user_tracking_id, ga_client_id, lms_ip = parse_tracking_context(self.user)
        context = {
            'ip': lms_ip,
            'Google Analytics': {
                'clientId': ga_client_id
            }
        }

        mixin.handle_payment({}, basket)

        # Verify the correct events are fired to Segment
        calls = []

        properties = translate_basket_line_for_segment(basket.lines.first())
        properties['cart_id'] = basket.id
        calls.append(mock.call(user_tracking_id, 'Product Added', properties, context=context))

        properties = {
            'checkout_id': basket.order_number,
            'step': 1,
            'payment_method': 'Visa | ' + DummyProcessor.NAME,
        }
        calls.append(mock.call(user_tracking_id, 'Checkout Step Completed', properties, context=context))
        properties['step'] = 2
        calls.append(mock.call(user_tracking_id, 'Checkout Step Viewed', properties, context=context))
        calls.append(mock.call(user_tracking_id, 'Checkout Step Completed', properties, context=context))

        properties = {'checkout_id': basket.order_number}
        calls.append(mock.call(user_tracking_id, 'Payment Info Entered', properties, context=context))

        mock_track.assert_has_calls(calls)
