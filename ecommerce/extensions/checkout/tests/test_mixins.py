"""
Tests for the ecommerce.extensions.checkout.mixins module.
"""


import ddt
import mock
from oscar.core.loading import get_class, get_model
from oscar.test.factories import BasketFactory, ProductFactory
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
from ecommerce.extensions.basket.constants import EMAIL_OPT_IN_ATTRIBUTE, PURCHASER_BEHALF_ATTRIBUTE
from ecommerce.extensions.basket.utils import basket_add_organization_attribute
from ecommerce.extensions.checkout.exceptions import BasketNotFreeError
from ecommerce.extensions.checkout.mixins import OFFER_ASSIGNED, OFFER_REDEEMED, EdxOrderPlacementMixin
from ecommerce.extensions.fulfillment.status import ORDER
from ecommerce.extensions.offer.constants import DAY3, DAY10, DAY19
from ecommerce.extensions.payment.tests.mixins import PaymentEventsMixin
from ecommerce.extensions.payment.tests.processors import DummyProcessor
from ecommerce.extensions.refund.tests.mixins import RefundTestMixin
from ecommerce.extensions.test.factories import (
    CodeAssignmentNudgeEmailsFactory,
    CodeAssignmentNudgeEmailTemplatesFactory,
    EnterpriseOfferFactory,
    OfferAssignmentFactory,
    VoucherFactory,
    create_basket,
    create_order
)
from ecommerce.invoice.models import Invoice
from ecommerce.tests.factories import UserFactory
from ecommerce.tests.mixins import BusinessIntelligenceMixin
from ecommerce.tests.testcases import TransactionTestCase

LOGGER_NAME = 'ecommerce.extensions.analytics.utils'
Basket = get_model('basket', 'Basket')
BasketAttribute = get_model('basket', 'BasketAttribute')
BasketAttributeType = get_model('basket', 'BasketAttributeType')
NoShippingRequired = get_class('shipping.methods', 'NoShippingRequired')
OfferAssignment = get_model('offer', 'OfferAssignment')
CodeAssignmentNudgeEmails = get_model('offer', 'CodeAssignmentNudgeEmails')
OrderTotalCalculator = get_class('checkout.calculators', 'OrderTotalCalculator')
PaymentEventType = get_model('order', 'PaymentEventType')
SourceType = get_model('payment', 'SourceType')
Product = get_model('catalogue', 'Product')
VoucherApplication = get_model('voucher', 'VoucherApplication')
Voucher = get_model('voucher', 'Voucher')


@ddt.ddt
@mock.patch.object(SegmentClient, 'track')
class EdxOrderPlacementMixinTests(BusinessIntelligenceMixin, PaymentEventsMixin, RefundTestMixin, TransactionTestCase):
    """
    Tests validating generic behaviors of the EdxOrderPlacementMixin.
    """

    def setUp(self):
        super(EdxOrderPlacementMixinTests, self).setUp()
        self.user = UserFactory(lms_user_id=61710)
        self.order = self.create_order(status=ORDER.OPEN)

        # Ensure that the basket attribute type exists for these tests
        self.basket_attribute_type, _ = BasketAttributeType.objects.get_or_create(
            name=EMAIL_OPT_IN_ATTRIBUTE)

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

        with LogCapture(LOGGER_NAME) as logger:
            mixin.handle_payment({}, basket)
            logger.check_present(
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

        with LogCapture(LOGGER_NAME) as logger:
            EdxOrderPlacementMixin().handle_successful_order(self.order)
            # ensure event is being tracked
            self.assertTrue(mock_track.called)
            # ensure event data is correct
            self.assert_correct_event(
                mock_track,
                self.order,
                self.user.lms_user_id,
                tracking_context['ga_client_id'],
                tracking_context['lms_ip'],
                self.order.number,
                self.order.currency,
                self.order.user.email,
                self.order.total_excl_tax,
                self.order.total_excl_tax,        # value for revenue field is same as total.
                check_traits=True,
            )
            logger.check_present(
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
        request_data = {
            'organization': 'Dummy Business Client',
            PURCHASER_BEHALF_ATTRIBUTE: 'False',
        }
        # Manually add organization and purchaser attributes on the basket for testing
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
        request_data = {
            'organization': 'Dummy Business Client',
            PURCHASER_BEHALF_ATTRIBUTE: 'False',
        }
        # Manually add organization and purchaser attributes on the basket for testing
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
            self.user.lms_user_id,
            None,
            None,
            self.order.number,
            self.order.currency,
            self.order.user.email,
            self.order.total_excl_tax,
            self.order.total_excl_tax,            # value for revenue field is same as total.
            check_traits=True,
        )

    def test_order_no_lms_user_id(self, mock_track):
        """
        Ensure that expected values are substituted when no LMS user id
        was available.
        """
        tracking_context = {'ga_client_id': 'test-client-id', 'lms_user_id': 'test-user-id', 'lms_ip': '127.0.0.1'}
        self.user.tracking_context = tracking_context
        self.user.lms_user_id = None
        self.user.save()

        EdxOrderPlacementMixin().handle_successful_order(self.order)
        # ensure event is being tracked
        self.assertTrue(mock_track.called)
        # ensure event data is correct
        self.assert_correct_event(
            mock_track,
            self.order,
            ECOM_TRACKING_ID_FMT.format(self.user.id),
            tracking_context['ga_client_id'],
            tracking_context['lms_ip'],
            self.order.number,
            self.order.currency,
            self.order.user.email,
            self.order.total_excl_tax,
            self.order.total_excl_tax,  # value for revenue field is same as total.
            check_traits=True,
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
        mock_log_exc.assert_called_with("Failed to emit tracking event upon order completion.")

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
            mock_delay.assert_called_once_with(self.order.number, site_code=self.partner.short_code, email_opt_in=False)

    def test_handle_successful_order_no_email_opt_in(self, _):
        """
        Verify that the post checkout defaults email_opt_in to false.
        """
        with mock.patch('ecommerce.extensions.checkout.mixins.post_checkout.send') as mock_send:
            mixin = EdxOrderPlacementMixin()
            mixin.handle_successful_order(self.order)
            send_arguments = {'sender': mixin, 'order': self.order, 'request': None, 'email_opt_in': False}
            mock_send.assert_called_once_with(**send_arguments)

    @ddt.data(True, False)
    def test_handle_successful_order_with_email_opt_in(self, expected_opt_in, _):
        """
        Verify that the post checkout sets email_opt_in if it is given.
        """
        BasketAttribute.objects.get_or_create(
            basket=self.order.basket,
            attribute_type=self.basket_attribute_type,
            value_text=expected_opt_in,
        )

        with mock.patch('ecommerce.extensions.checkout.mixins.post_checkout.send') as mock_send:
            mixin = EdxOrderPlacementMixin()
            mixin.handle_successful_order(self.order)
            send_arguments = {
                'sender': mixin,
                'order': self.order,
                'request': None,
                'email_opt_in': expected_opt_in,
            }
            mock_send.assert_called_once_with(**send_arguments)

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
            },
            'page': {
                'url': 'https://testserver.fake/'
            },
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

        properties = {
            'basket_id': basket.id,
            'total': basket.total_incl_tax,
            'success': True,
            'processor_name': DummyProcessor.NAME,
            'stripe_enabled': False,
        }
        calls.append(mock.call(user_tracking_id, 'Payment Processor Response', properties, context=context))

        mock_track.assert_has_calls(calls)

    @mock.patch.object(DummyProcessor, 'handle_processor_response', mock.Mock(side_effect=Exception))
    def test_payment_not_accepted_segment_logging(self, mock_track):
        """
        Verify if the payment is not accepted, we still log the processor response
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
            },
            'page': {
                'url': 'https://testserver.fake/'
            },
        }
        with self.assertRaises(Exception):
            mixin.handle_payment({}, basket)

        # Verify the correct events are fired to Segment
        calls = []

        properties = translate_basket_line_for_segment(basket.lines.first())
        properties['cart_id'] = basket.id
        calls.append(mock.call(user_tracking_id, 'Product Added', properties, context=context))

        properties = {
            'basket_id': basket.id,
            'payment_error': 'Exception',
            'success': False,
            'processor_name': DummyProcessor.NAME,
            'stripe_enabled': False,
        }
        calls.append(mock.call(user_tracking_id, 'Payment Processor Response', properties, context=context))

        mock_track.assert_has_calls(calls)

    def test_update_assigned_voucher_offer_assignment(self, __):
        """
        Verify the "update_assigned_voucher_offer_assignment" works as expected.
        """
        enterprise_offer = EnterpriseOfferFactory()
        voucher = VoucherFactory()
        voucher.offers.add(enterprise_offer)
        basket = create_basket(owner=self.user, site=self.site)
        basket.vouchers.add(voucher)
        order = create_order(user=self.user, basket=basket)
        voucher_application = VoucherApplication.objects.create(voucher=voucher, user=self.user, order=order)
        offer_assignment = OfferAssignmentFactory(offer=enterprise_offer, code=voucher.code, user_email=self.user.email)

        # create nudge email templates and subscription records
        for email_type in (DAY3, DAY10, DAY19):
            nudge_email_template = CodeAssignmentNudgeEmailTemplatesFactory(email_type=email_type)
            nudge_email = CodeAssignmentNudgeEmailsFactory(
                email_template=nudge_email_template,
                user_email=self.user.email,
                code=voucher.code
            )

            # verify subscription is active
            assert nudge_email.is_subscribed

        EdxOrderPlacementMixin().update_assigned_voucher_offer_assignment(order)

        offer_assignment = OfferAssignment.objects.get(id=offer_assignment.id)
        assert offer_assignment.status == OFFER_REDEEMED
        assert offer_assignment.voucher_application == voucher_application

        # verify that nudge emails subscriptions are inactive
        assert CodeAssignmentNudgeEmails.objects.filter(is_subscribed=True).count() == 0
        assert CodeAssignmentNudgeEmails.objects.filter(
            code__in=[voucher.code],
            user_email__in=[self.user.email],
            is_subscribed=False
        ).count() == 3

    def test_create_assignments_for_multi_use_per_customer(self, __):
        """
        Verify the `create_assignments_for_multi_use_per_customer` works as expected for `MULTI_USE_PER_CUSTOMER`.
        """
        coupon_max_global_applications = 10
        enterprise_offer = EnterpriseOfferFactory(max_global_applications=coupon_max_global_applications)
        voucher = VoucherFactory(usage=Voucher.MULTI_USE_PER_CUSTOMER)
        voucher.offers.add(enterprise_offer)
        basket = create_basket(owner=self.user, site=self.site)
        basket.vouchers.add(voucher)
        order = create_order(user=self.user, basket=basket)

        assert OfferAssignment.objects.all().count() == 0

        EdxOrderPlacementMixin().create_assignments_for_multi_use_per_customer(order)
        EdxOrderPlacementMixin().update_assigned_voucher_offer_assignment(order)

        assert OfferAssignment.objects.all().count() == coupon_max_global_applications
        assert OfferAssignment.objects.filter(
            offer=enterprise_offer, code=voucher.code, user_email=basket.owner.email, status=OFFER_ASSIGNED
        ).count() == 9
        assert OfferAssignment.objects.filter(
            offer=enterprise_offer, code=voucher.code, user_email=basket.owner.email, status=OFFER_REDEEMED
        ).count() == 1

    def test_create_offer_assignments_for_updated_max_uses(self, __):
        """
        Verify the `create_assignments_for_multi_use_per_customer` works as expected for
        `MULTI_USE_PER_CUSTOMER` when `max_global_applications` is updated for existing voucher.
        """
        coupon_max_global_applications = 1
        enterprise_offer = EnterpriseOfferFactory(max_global_applications=coupon_max_global_applications)
        voucher = VoucherFactory(usage=Voucher.MULTI_USE_PER_CUSTOMER)
        voucher.offers.add(enterprise_offer)
        basket = create_basket(owner=self.user, site=self.site)
        basket.vouchers.add(voucher)
        order = create_order(user=self.user, basket=basket)

        assert OfferAssignment.objects.all().count() == 0

        EdxOrderPlacementMixin().create_assignments_for_multi_use_per_customer(order)
        EdxOrderPlacementMixin().update_assigned_voucher_offer_assignment(order)

        assert OfferAssignment.objects.all().count() == coupon_max_global_applications
        assert OfferAssignment.objects.filter(
            offer=enterprise_offer, code=voucher.code, user_email=basket.owner.email, status=OFFER_REDEEMED
        ).count() == 1

        # update max_global_applications
        coupon_new_max_global_applications = 5
        enterprise_offer.max_global_applications = coupon_new_max_global_applications
        enterprise_offer.save()

        assert voucher.enterprise_offer.max_global_applications == coupon_new_max_global_applications

        EdxOrderPlacementMixin().create_assignments_for_multi_use_per_customer(order)

        assert OfferAssignment.objects.all().count() == coupon_new_max_global_applications
        assert OfferAssignment.objects.filter(
            offer=enterprise_offer, code=voucher.code, user_email=basket.owner.email, status=OFFER_ASSIGNED
        ).count() == 4
        assert OfferAssignment.objects.filter(
            offer=enterprise_offer, code=voucher.code, user_email=basket.owner.email, status=OFFER_REDEEMED
        ).count() == 1

        # call once again to verify nothing is created because all available slots are assigned
        EdxOrderPlacementMixin().create_assignments_for_multi_use_per_customer(order)
        assert OfferAssignment.objects.all().count() == coupon_new_max_global_applications
