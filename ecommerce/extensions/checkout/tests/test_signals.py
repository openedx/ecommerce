

import mock
import responses
from django.core import mail
from opaque_keys.edx.keys import CourseKey
from oscar.core.loading import get_class, get_model
from oscar.test import factories
from testfixtures import LogCapture

from ecommerce.core.constants import ENROLLMENT_CODE_PRODUCT_CLASS_NAME
from ecommerce.core.tests import toggle_switch
from ecommerce.coupons.tests.mixins import CouponMixin
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.courses.utils import mode_for_product
from ecommerce.extensions.basket.tests.test_utils import TEST_BUNDLE_ID
from ecommerce.extensions.checkout.signals import send_course_purchase_email, track_completed_order
from ecommerce.extensions.checkout.utils import get_receipt_page_url
from ecommerce.extensions.test.factories import create_order, prepare_voucher
from ecommerce.programs.tests.mixins import ProgramTestMixin
from ecommerce.tests.factories import ProductFactory
from ecommerce.tests.testcases import TestCase

Applicator = get_class('offer.applicator', 'Applicator')
BasketAttribute = get_model('basket', 'BasketAttribute')
BasketAttributeType = get_model('basket', 'BasketAttributeType')
Benefit = get_model('offer', 'Benefit')
Condition = get_model('offer', 'Condition')
ConditionalOffer = get_model('offer', 'ConditionalOffer')
Product = get_model('catalogue', 'Product')

BUNDLE = 'bundle_identifier'
LOGGER_NAME = 'ecommerce.extensions.checkout.signals'


class SignalTests(ProgramTestMixin, CouponMixin, TestCase):
    def setUp(self):
        super(SignalTests, self).setUp()
        self.user = self.create_user(email="example@example.com")
        self.request.user = self.user
        toggle_switch('ENABLE_NOTIFICATIONS', True)

    def prepare_order(self, seat_type, credit_provider_id=None, price=50):
        """
        Prepares order for a post-checkout test.

        Args:
            seat_type (str): Course seat type
            credit_provider_id (str): Credit provider associated with the course seat.
            price : Price of the course

        Returns:
            Order
        """
        course = CourseFactory(partner=self.partner)
        seat = course.create_or_update_seat(seat_type, False, price, credit_provider_id, None, 2)
        basket = factories.BasketFactory(owner=self.user, site=self.site)
        basket.add_product(seat, 1)
        order = create_order(basket=basket, user=self.user)
        return order

    def prepare_coupon_order(self):
        coupon = self.create_coupon()
        basket = factories.BasketFactory(owner=self.user, site=self.site)
        basket.add_product(coupon, 1)
        order = create_order(number=1, basket=basket, user=self.user)
        return order

    def mock_get_program_data(self, is_full):
        data = {'title': 'test_program', 'courses': [{}]}
        if is_full:
            data['courses'].append({})
        return data

    @responses.activate
    def test_post_checkout_callback(self):
        """
        When the post_checkout signal is emitted, the receiver should attempt
        to fulfill the newly-placed order and send receipt email.
        """
        credit_provider_id = 'HGW'
        credit_provider_name = 'Hogwarts'
        body = {'display_name': credit_provider_name}
        responses.add(
            responses.GET,
            self.site.siteconfiguration.build_lms_url(
                'api/credit/v1/providers/{credit_provider_id}/'.format(credit_provider_id=credit_provider_id)
            ),
            json=body,
            content_type='application/json'
        )

        order = self.prepare_order('credit', credit_provider_id=credit_provider_id)
        self.mock_access_token_response()
        send_course_purchase_email(None, user=self.user, order=order)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].from_email, order.site.siteconfiguration.from_email)
        self.assertEqual(mail.outbox[0].subject, 'Order Receipt')
        self.assertEqual(
            mail.outbox[0].body,
            '\nPayment confirmation for: {course_title}'
            '\n\nDear {full_name},'
            '\n\nThank you for purchasing {credit_hours} credit hours from {credit_provider_name} for {course_title}. '
            'A charge will appear on your credit or debit card statement with a company name of "{platform_name}".'
            '\n\nTo receive your course credit, you must also request credit at the {credit_provider_name} website. '
            'For a link to request credit from {credit_provider_name}, or to see the status of your credit request, '
            'go to your {platform_name} dashboard.'
            '\n\nTo explore other credit-eligible courses, visit the {platform_name} website. '
            'We add new courses frequently!'
            '\n\nTo view your payment information, visit the following website.'
            '\n{receipt_url}'
            '\n\nThank you. We hope you enjoyed your course!'
            '\nThe {platform_name} team'
            '\n\nYou received this message because you purchased credit hours for {course_title}, '
            'an {platform_name} course.\n'.format(
                course_title=order.lines.first().product.title,
                full_name=self.user.get_full_name(),
                credit_hours=2,
                credit_provider_name=credit_provider_name,
                platform_name=self.site.name,
                receipt_url=get_receipt_page_url(
                    self.request,
                    order_number=order.number,
                    site_configuration=order.site.siteconfiguration
                )
            )
        )

    def test_post_checkout_callback_non_credit_course(self):
        """
        Test that if basket has a seat product and no credit provider
        is present, then send course purchase email
        """
        order = self.prepare_order('verified')
        send_course_purchase_email(None, user=self.user, order=order)
        product = order.lines.first().product
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].from_email, order.site.siteconfiguration.from_email)
        self.assertEqual(mail.outbox[0].subject, 'Order Placed')
        self.assertIn(product.title, mail.outbox[0].body)

    def test_post_checkout_callback_free_checkout(self):
        """
        Test that during freecheckout no email is sent
        """
        order = self.prepare_order('verified', price=0)
        send_course_purchase_email(None, user=self.user, order=order)
        self.assertEqual(len(mail.outbox), 0)

    def test_post_checkout_callback_no_credit_provider(self):
        """
        Test that if no credit_provider_id is present for credit course,
        error is logged
        """
        order = self.prepare_order('credit')
        with LogCapture(LOGGER_NAME) as logger:
            send_course_purchase_email(None, user=self.user, order=order)
            logger.check(
                (
                    LOGGER_NAME,
                    'ERROR',
                    'Failed to send credit receipt notification. Credit seat product [{}] has no provider.'.format(
                        order.lines.first().product.id
                    )
                )
            )

    def test_post_checkout_callback_no_provider_data(self):
        """
        Test that if no provider data is present against a credit provider
        id, no email is sent
        """
        order = self.prepare_order('credit', credit_provider_id='HGW')
        send_course_purchase_email(None, user=self.user, order=order)
        self.assertEqual(len(mail.outbox), 0)

    def test_post_checkout_callback_entitlement_product(self):
        """
        Test that order placement email is sent if learner purchases
        entitlement
        """
        entitlement = self.create_entitlement_product()
        basket = factories.BasketFactory(owner=self.user, site=self.site)
        basket.add_product(entitlement)
        order = create_order(basket=basket, user=self.user)
        send_course_purchase_email(None, user=self.user, order=order)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].from_email, order.site.siteconfiguration.from_email)
        self.assertEqual(mail.outbox[0].subject, 'Order Placed')
        self.assertIn(entitlement.title, mail.outbox[0].body)

    def test_post_checkout_callback_non_seat_or_entitlement_product(self):
        """
        Test that no email is sent if basket contains a single product
        of non seat or non entitlement type
        """
        order = self.prepare_coupon_order()
        send_course_purchase_email(None, user=self.user, order=order)
        self.assertEqual(len(mail.outbox), 0)

    def test_more_than_one_product(self):
        """
        Test that we do not send email if basket contains more
        than one product
        """
        coupon = self.create_coupon()
        course = CourseFactory(partner=self.partner)
        seat = course.create_or_update_seat('verified', False, 50, None, None, 2)
        basket = factories.BasketFactory(owner=self.user, site=self.site)
        basket.add_product(seat)
        basket.add_product(coupon)
        order = create_order(basket=basket, user=self.user)

        with LogCapture(LOGGER_NAME) as logger:
            send_course_purchase_email(None, user=self.user, order=order)
            logger.check(
                (
                    LOGGER_NAME,
                    'INFO',
                    'Currently support receipt emails for order with one item.'
                )
            )

    def _generate_event_properties(
            self, order, voucher=None, bundle_id=None, fullBundle=False):
        coupon = voucher.code if voucher else None
        products = []
        for line in order.lines.all():
            order_line = {
                'id': line.partner_sku,
                'sku': mode_for_product(line.product),
                'name': line.product.course.id if line.product.course else line.product.title,
                'price': float(line.line_price_excl_tax),
                'quantity': line.quantity,
                'category': line.product.get_product_class().name,
                'title': line.product.title,
            }
            products.append(order_line)

        properties = {
            'orderId': order.number,
            'total': float(order.total_excl_tax),
            'revenue': float(order.total_excl_tax),
            'currency': order.currency,
            'coupon': coupon,
            'discount': float(order.total_discount_incl_tax),
            'products': products,
            'stripe_enabled': False,
            'processor_name': None
        }
        if order.user:
            properties['email'] = order.user.email
        if bundle_id:
            program = self.mock_get_program_data(fullBundle)
            if len(order.lines.all()) < len(program['courses']):
                variant = 'partial'
            else:
                variant = 'full'

            bundle_product = {
                'id': bundle_id,
                'price': 0,
                'quantity': len(order.lines.all()),
                'category': 'bundle',
                'variant': variant,
                'name': program['title']
            }
            properties['products'].append(bundle_product)

        return properties

    def _get_recommendations_data(self, order):
        course_keys = []
        for line in order.lines.all():
            if line.product.course:
                course_key = CourseKey.from_string(line.product.course.id)
                course_key = f'{course_key.org}+{course_key.course}'
                course_keys.append(course_key)
        return {
            'course_keys': course_keys,
            'is_control': True
        }

    def test_track_completed_order(self):
        """ An event should be sent to Segment. """

        with mock.patch('ecommerce.extensions.checkout.signals.track_segment_event') as mock_track:
            order = self.prepare_order('verified')
            track_completed_order(None, order)
            properties = self._generate_event_properties(order)
            mock_track.assert_called_once_with(order.site, order.user, 'Order Completed', properties, traits=properties)

            # We should be able to fire events even if the product is not related to a course.
            mock_track.reset_mock()
            order = create_order()
            track_completed_order(None, order)
            properties = self._generate_event_properties(order)
            mock_track.assert_called_once_with(order.site, order.user, 'Order Completed', properties, traits=properties)

    @mock.patch('ecommerce.extensions.checkout.signals.track_segment_event')
    def test_track_bundle_order(self, mock_track):
        """ If the order is a bundle purchase, we should track the associated bundle in the properties """
        order = self.prepare_order('verified')
        BasketAttribute.objects.update_or_create(
            basket=order.basket,
            attribute_type=BasketAttributeType.objects.get(name=BUNDLE),
            value_text=TEST_BUNDLE_ID
        )

        # Tracks a full bundle order
        with mock.patch('ecommerce.extensions.checkout.signals.get_program',
                        mock.Mock(return_value=self.mock_get_program_data(True))):
            track_completed_order(None, order)
            properties = self._generate_event_properties(
                order, bundle_id=TEST_BUNDLE_ID, fullBundle=True
            )
            mock_track.assert_called_once_with(order.site, order.user, 'Order Completed', properties, traits=properties)

        # Tracks a partial bundle order
        with mock.patch('ecommerce.extensions.checkout.signals.get_program',
                        mock.Mock(return_value=self.mock_get_program_data(False))):
            mock_track.reset_mock()
            track_completed_order(None, order)
            properties = self._generate_event_properties(order, bundle_id=TEST_BUNDLE_ID)
            mock_track.assert_called_once_with(order.site, order.user, 'Order Completed', properties, traits=properties)

    def test_track_completed_discounted_order_with_voucher(self):
        """ An event including coupon information should be sent to Segment"""
        with mock.patch('ecommerce.extensions.checkout.signals.track_segment_event') as mock_track:
            # Orders may be discounted by percent
            percent_benefit = 66
            product = ProductFactory(categories=[], stockrecords__price_currency='USD')
            _range = factories.RangeFactory(products=[product], )
            voucher, product = prepare_voucher(_range=_range, benefit_value=percent_benefit)

            basket = factories.BasketFactory(owner=self.user, site=self.site)
            basket.add_product(product)
            basket.vouchers.add(voucher)
            Applicator().apply(basket, user=basket.owner, request=self.request)

            order = factories.create_order(basket=basket, user=self.user)
            track_completed_order(None, order)
            properties = self._generate_event_properties(order, voucher)
            mock_track.assert_called_once_with(order.site, order.user, 'Order Completed', properties, traits=properties)

    def test_track_completed_discounted_order_with_voucher_with_offer(self):
        with mock.patch('ecommerce.extensions.checkout.signals.track_segment_event') as mock_track:
            # Orders may be discounted by a fixed value
            fixed_benefit = 5.00
            offer_discount = 6
            product = ProductFactory(categories=[], stockrecords__price_currency='USD')
            _range = factories.RangeFactory(products=[product], )
            voucher, product = prepare_voucher(_range=_range, benefit_value=fixed_benefit, benefit_type=Benefit.FIXED)
            factories.ConditionalOfferFactory(
                offer_type=ConditionalOffer.SITE,
                benefit=factories.BenefitFactory(range=_range, value=offer_discount),
                condition=factories.ConditionFactory(type=Condition.COVERAGE, value=1, range=_range)
            )

            basket = factories.BasketFactory(owner=self.user, site=self.site)
            basket.add_product(product)
            basket.vouchers.add(voucher)
            Applicator().apply(basket, user=basket.owner, request=self.request)

            order = factories.create_order(basket=basket, user=self.user)
            track_completed_order(None, order)
            properties = self._generate_event_properties(order, voucher)
            mock_track.assert_called_once_with(order.site, order.user, 'Order Completed', properties, traits=properties)

    def test_track_completed_discounted_order_with_offer(self):
        """ An event including a discount but no coupon should be sent to Segment"""
        with mock.patch('ecommerce.extensions.checkout.signals.track_segment_event') as mock_track:
            # Orders may be discounted by a fixed value
            offer_discount = 5
            product = ProductFactory(categories=[], stockrecords__price_currency='USD')
            _range = factories.RangeFactory(products=[product], )
            site_offer = factories.ConditionalOfferFactory(
                offer_type=ConditionalOffer.SITE,
                benefit=factories.BenefitFactory(range=_range, value=offer_discount),
                condition=factories.ConditionFactory(type=Condition.COVERAGE, value=1, range=_range)
            )

            basket = factories.BasketFactory(owner=self.user, site=self.site)
            basket.add_product(product)
            Applicator().apply_offers(basket, [site_offer])

            order = factories.create_order(basket=basket, user=self.user)
            track_completed_order(None, order)
            properties = self._generate_event_properties(order)
            mock_track.assert_called_once_with(order.site, order.user, 'Order Completed', properties, traits=properties)

    def test_track_completed_coupon_order(self):
        """ Make sure we do not send GA events for Coupon orders """
        with mock.patch('ecommerce.extensions.checkout.signals.track_segment_event') as mock_track:
            order = self.prepare_coupon_order()
            track_completed_order(None, order)
            assert not mock_track.called

    def test_track_completed_enrollment_order(self):
        """ Make sure we are sending GA events for Enrollment Code orders """
        with mock.patch('ecommerce.extensions.checkout.signals.track_segment_event') as mock_track:

            course = CourseFactory(partner=self.partner)
            course.create_or_update_seat('verified', True, 50, create_enrollment_code=True)
            enrollment_code = Product.objects.get(product_class__name=ENROLLMENT_CODE_PRODUCT_CLASS_NAME)

            basket = factories.BasketFactory(owner=self.user, site=self.site)
            basket.add_product(enrollment_code)

            order = factories.create_order(basket=basket, user=self.user)
            track_completed_order(None, order)
            assert mock_track.called
