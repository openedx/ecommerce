import json

import httpretty
import mock
from django.core import mail
from oscar.core.loading import get_class, get_model
from oscar.test import factories
from oscar.test.newfactories import BasketFactory
from testfixtures import LogCapture

from ecommerce.core.constants import ENROLLMENT_CODE_PRODUCT_CLASS_NAME, ENROLLMENT_CODE_SWITCH
from ecommerce.core.tests import toggle_switch
from ecommerce.coupons.tests.mixins import CouponMixin
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.courses.utils import mode_for_product
from ecommerce.extensions.checkout.signals import send_course_purchase_email, track_completed_order
from ecommerce.extensions.checkout.utils import get_receipt_page_url
from ecommerce.extensions.test.factories import create_order, prepare_voucher
from ecommerce.programs.tests.mixins import ProgramTestMixin
from ecommerce.tests.factories import ProductFactory
from ecommerce.tests.testcases import TestCase

Applicator = get_class('offer.utils', 'Applicator')
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
        self.user = self.create_user()
        self.request.user = self.user
        toggle_switch('ENABLE_NOTIFICATIONS', True)

    def prepare_order(self, seat_type, credit_provider_id=None):
        """
        Prepares order for a post-checkout test.

        Args:
            seat_type (str): Course seat type
            credit_provider_id (str): Credit provider associated with the course seat.

        Returns:
            Order
        """
        course = CourseFactory()
        seat = course.create_or_update_seat(seat_type, False, 50, self.partner, credit_provider_id, None, 2)
        basket = BasketFactory(owner=self.user, site=self.site)
        basket.add_product(seat, 1)
        order = create_order(basket=basket, user=self.user)
        return order

    def mock_get_program_data(self, isFull):
        data = {'title': 'test_program', 'courses': [{}]}
        if isFull:
            data['courses'].append({})
        return data

    @httpretty.activate
    def test_post_checkout_callback(self):
        """
        When the post_checkout signal is emitted, the receiver should attempt
        to fulfill the newly-placed order and send receipt email.
        """
        credit_provider_id = 'HGW'
        credit_provider_name = 'Hogwarts'
        body = {'display_name': credit_provider_name}
        httpretty.register_uri(
            httpretty.GET,
            self.site.siteconfiguration.build_lms_url(
                'api/credit/v1/providers/{credit_provider_id}/'.format(credit_provider_id=credit_provider_id)
            ),
            body=json.dumps(body),
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
                    order_number=order.number,
                    site_configuration=order.site.siteconfiguration
                )
            )
        )

    def test_post_checkout_callback_no_credit_provider(self):
        order = self.prepare_order('verified')
        with LogCapture(LOGGER_NAME) as l:
            send_course_purchase_email(None, user=self.user, order=order)
            l.check(
                (
                    LOGGER_NAME,
                    'ERROR',
                    'Failed to send credit receipt notification. Credit seat product [{}] has no provider.'.format(
                        order.lines.first().product.id
                    )
                )
            )

    def _generate_event_properties(self, order, voucher=None, bundle_id=None, fullBundle=False):
        coupon = voucher.code if voucher else None
        properties = {
            'orderId': order.number,
            'total': str(order.total_excl_tax),
            'currency': order.currency,
            'coupon': coupon,
            'discount': str(order.total_discount_incl_tax),
            'products': [
                {
                    'id': line.partner_sku,
                    'sku': mode_for_product(line.product),
                    'name': line.product.course.id if line.product.course else line.product.title,
                    'price': str(line.line_price_excl_tax),
                    'quantity': line.quantity,
                    'category': line.product.get_product_class().name,
                } for line in order.lines.all()
            ],
        }
        if bundle_id:
            program = self.mock_get_program_data(fullBundle)
            if len(order.lines.all()) < len(program['courses']):
                variant = 'partial'
            else:
                variant = 'full'

            bundle_product = {
                'id': bundle_id,
                'price': '0',
                'quantity': str(len(order.lines.all())),
                'category': 'bundle',
                'variant': variant,
                'name': program['title']
            }
            properties['products'].append(bundle_product)

        return properties

    def test_track_completed_order(self):
        """ An event should be sent to Segment. """

        with mock.patch('ecommerce.extensions.checkout.signals.track_segment_event') as mock_track:
            order = self.prepare_order('verified')
            track_completed_order(None, order)
            properties = self._generate_event_properties(order)
            mock_track.assert_called_once_with(order.site, order.user, 'Order Completed', properties)

            # We should be able to fire events even if the product is not related to a course.
            mock_track.reset_mock()
            order = create_order()
            track_completed_order(None, order)
            properties = self._generate_event_properties(order)
            mock_track.assert_called_once_with(order.site, order.user, 'Order Completed', properties)

    @mock.patch('ecommerce.extensions.checkout.signals.track_segment_event')
    def test_track_bundle_order(self, mock_track):
        """ If the order is a bundle purchase, we should track the associated bundle in the properties """
        order = self.prepare_order('verified')
        BasketAttribute.objects.update_or_create(
            basket=order.basket,
            attribute_type=BasketAttributeType.objects.get(name=BUNDLE),
            value_text='test_bundle'
        )

        # Tracks a full bundle order
        with mock.patch('ecommerce.extensions.checkout.signals.get_program',
                        mock.Mock(return_value=self.mock_get_program_data(True))):
            track_completed_order(None, order)
            properties = self._generate_event_properties(order, bundle_id='test_bundle', fullBundle=True)
            mock_track.assert_called_once_with(order.site, order.user, 'Order Completed', properties)

        # Tracks a partial bundle order
        with mock.patch('ecommerce.extensions.checkout.signals.get_program',
                        mock.Mock(return_value=self.mock_get_program_data(False))):
            mock_track.reset_mock()
            track_completed_order(None, order)
            properties = self._generate_event_properties(order, bundle_id='test_bundle')
            mock_track.assert_called_once_with(order.site, order.user, 'Order Completed', properties)

    def test_track_completed_discounted_order_with_voucher(self):
        """ An event including coupon information should be sent to Segment"""
        with mock.patch('ecommerce.extensions.checkout.signals.track_segment_event') as mock_track:
            # Orders may be discounted by percent
            percent_benefit = 66
            product = ProductFactory(categories=[], stockrecords__price_currency='USD')
            _range = factories.RangeFactory(products=[product], )
            voucher, product = prepare_voucher(_range=_range, benefit_value=percent_benefit)

            basket = BasketFactory(owner=self.user, site=self.site)
            basket.add_product(product)
            basket.vouchers.add(voucher)
            Applicator().apply(basket, user=basket.owner, request=self.request)

            order = factories.create_order(basket=basket, user=self.user)
            track_completed_order(None, order)
            properties = self._generate_event_properties(order, voucher)
            mock_track.assert_called_once_with(order.site, order.user, 'Order Completed', properties)

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

            basket = BasketFactory(owner=self.user, site=self.site)
            basket.add_product(product)
            basket.vouchers.add(voucher)
            Applicator().apply(basket, user=basket.owner, request=self.request)

            order = factories.create_order(basket=basket, user=self.user)
            track_completed_order(None, order)
            properties = self._generate_event_properties(order, voucher)
            mock_track.assert_called_once_with(order.site, order.user, 'Order Completed', properties)

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

            basket = BasketFactory(owner=self.user, site=self.site)
            basket.add_product(product)
            Applicator().apply_offers(basket, [site_offer])

            order = factories.create_order(basket=basket, user=self.user)
            track_completed_order(None, order)
            properties = self._generate_event_properties(order)
            mock_track.assert_called_once_with(order.site, order.user, 'Order Completed', properties)

    def test_track_completed_coupon_order(self):
        """ Make sure we do not send GA events for Coupon orders """
        with mock.patch('ecommerce.extensions.checkout.signals.track_segment_event') as mock_track:

            coupon = self.create_coupon()
            basket = BasketFactory(owner=self.user, site=self.site)
            basket.add_product(coupon)

            order = factories.create_order(basket=basket, user=self.user)
            track_completed_order(None, order)
            assert not mock_track.called

    def test_track_completed_enrollment_order(self):
        """ Make sure we do not send GA events for Enrollment Code orders """
        with mock.patch('ecommerce.extensions.checkout.signals.track_segment_event') as mock_track:

            toggle_switch(ENROLLMENT_CODE_SWITCH, True)
            site_config = self.site.siteconfiguration
            site_config.enable_enrollment_codes = True
            site_config.save()

            course = CourseFactory()
            course.create_or_update_seat('verified', True, 50, self.partner, create_enrollment_code=True)
            enrollment_code = Product.objects.get(product_class__name=ENROLLMENT_CODE_PRODUCT_CLASS_NAME)

            basket = BasketFactory(owner=self.user, site=self.site)
            basket.add_product(enrollment_code)

            order = factories.create_order(basket=basket, user=self.user)
            track_completed_order(None, order)
            assert not mock_track.called
