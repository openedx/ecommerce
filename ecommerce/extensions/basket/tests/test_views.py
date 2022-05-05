import datetime
import urllib.error
import urllib.parse
from contextlib import contextmanager
from decimal import Decimal

import ddt
import mock
import responses
from django.conf import settings
from django.test import override_settings
from django.urls import reverse
from edx_django_utils.cache import RequestCache
from oscar.core.loading import get_class, get_model
from oscar.test import factories
from requests.exceptions import ConnectionError as ReqConnectionError
from testfixtures import LogCapture

from ecommerce.core.url_utils import absolute_url
from ecommerce.coupons.tests.mixins import DiscoveryMockMixin
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.enterprise.tests.mixins import EnterpriseServiceMockMixin
from ecommerce.enterprise.utils import construct_enterprise_course_consent_url
from ecommerce.entitlements.utils import create_or_update_course_entitlement
from ecommerce.extensions.analytics.utils import translate_basket_line_for_segment
from ecommerce.extensions.basket.constants import ENABLE_STRIPE_PAYMENT_PROCESSOR
from ecommerce.extensions.basket.tests.mixins import BasketMixin
from ecommerce.extensions.basket.tests.test_utils import TEST_BUNDLE_ID
from ecommerce.extensions.basket.utils import _set_basket_bundle_status, apply_voucher_on_basket_and_check_discount
from ecommerce.extensions.test.factories import prepare_voucher
from ecommerce.tests.factories import ProductFactory
from ecommerce.tests.mixins import LmsApiMockMixin
from ecommerce.tests.testcases import TestCase

Applicator = get_class('offer.applicator', 'Applicator')
BasketAttribute = get_model('basket', 'BasketAttribute')
BasketAttributeType = get_model('basket', 'BasketAttributeType')
Benefit = get_model('offer', 'Benefit')
Condition = get_model('offer', 'Condition')
ConditionalOffer = get_model('offer', 'ConditionalOffer')
Selector = get_class('partner.strategy', 'Selector')
Voucher = get_model('voucher', 'Voucher')
VoucherApplication = get_model('voucher', 'VoucherApplication')

COUPON_CODE = 'COUPONTEST'
BUNDLE = 'bundle_identifier'


class BasketLogicTestMixin:
    """ Helper functions for Basket API and BasketSummaryView tests. """
    def create_empty_basket(self):
        basket = factories.BasketFactory(owner=self.user, site=self.site)
        return basket

    def create_basket_and_add_product(self, product):
        basket = self.create_empty_basket()
        basket.add_product(product, 1)
        return basket

    def create_seat(self, course, seat_price=100, cert_type='verified'):
        return course.create_or_update_seat(cert_type, True, seat_price)

    def create_and_apply_benefit_to_basket(self, basket, product, benefit_type, benefit_value):
        _range = factories.RangeFactory(products=[product, ])
        voucher, __ = prepare_voucher(_range=_range, benefit_type=benefit_type, benefit_value=benefit_value)
        basket.vouchers.add(voucher)
        Applicator().apply(basket)
        return voucher

    @contextmanager
    def assert_events_fired_to_segment(self, basket):
        with mock.patch('ecommerce.extensions.basket.views.track_segment_event', return_value=(True, '')) as mock_track:
            yield

            calls = []
            properties = {
                'cart_id': basket.id,
                'products': [translate_basket_line_for_segment(line) for line in basket.all_lines()],
            }
            calls.append(mock.call(self.site, self.user, 'Cart Viewed', properties,))

            properties = {
                'checkout_id': basket.order_number,
                'step': 1
            }
            calls.append(mock.call(self.site, self.user, 'Checkout Step Viewed', properties))
            mock_track.assert_has_calls(calls)

    def verify_exception_logged_on_segment_error(self):
        """ Verify error log when track_segment_event fails. """
        seat = self.create_seat(self.course)
        basket = self.create_basket_and_add_product(seat)
        self.mock_access_token_response()
        self.mock_course_run_detail_endpoint(
            self.course, discovery_api_url=self.site_configuration.discovery_api_url
        )
        self.assertEqual(basket.lines.count(), 1)

        logger_name = 'ecommerce.extensions.basket.views'
        with LogCapture(logger_name) as logger:
            with mock.patch('ecommerce.extensions.basket.views.track_segment_event') as mock_track:
                mock_track.side_effect = Exception()

                response = self.client.get(self.path)
                self.assertEqual(response.status_code, 200)

                logger.check((
                    logger_name, 'ERROR',
                    u'Failed to fire Cart Viewed event for basket [{}]'.format(basket.id)
                ))


class PaymentApiResponseTestMixin(BasketLogicTestMixin):
    """
    Helpers for all payment api bff endpoints which return the complete payment api response.
    """
    def assert_empty_basket_response(
            self,
            basket,
            response=None,
            messages=None,
            status_code=200,
    ):
        self.assert_expected_response(
            basket=basket,
            response=response,
            messages=messages,
            status_code=status_code,
            currency=None,
            order_total=0,
            show_coupon_form=False,
            summary_price=0,
        )

    def assert_expected_response(
            self,
            basket,
            enable_stripe_payment_processor=False,
            url=None,
            response=None,
            status_code=200,
            product_type=u'Seat',
            currency=u'USD',
            discount_value=0,
            discount_type=Benefit.FIXED,
            certificate_type=u'verified',
            summary_price=100,
            voucher=None,
            offer_provider=None,
            show_coupon_form=True,
            image_url=None,
            title=None,
            subject=None,
            messages=None,
            summary_discounts=None,
            **kwargs
    ):
        if response is None:
            response = self.client.get(url if url else self.path)
        self.assertEqual(response.status_code, status_code)

        if summary_discounts is None:
            if discount_type == Benefit.FIXED:
                summary_discounts = discount_value
            else:
                summary_discounts = summary_price * (float(discount_value) / 100)

        order_total = round(summary_price - summary_discounts, 2)

        if discount_value:
            coupons = [{
                'benefit_type': discount_type,
                'benefit_value': discount_value,
                'code': u'COUPONTEST',
                'id': voucher.id,
            }]
        else:
            coupons = []

        if offer_provider:
            offers = [{
                'benefit_type': discount_type,
                'benefit_value': discount_value,
                'provider': offer_provider,
            }]
        else:
            offers = []

        expected_response = {
            'basket_id': basket.id,
            'currency': currency,
            'enable_stripe_payment_processor': enable_stripe_payment_processor,
            'offers': offers,
            'coupons': coupons,
            'messages': messages if messages else [],
            'is_free_basket': order_total == 0,
            'show_coupon_form': show_coupon_form,
            'summary_discounts': summary_discounts,
            'summary_price': summary_price,
            'order_total': order_total,
            'products': [
                {
                    'product_type': product_type,
                    'certificate_type': certificate_type,
                    'image_url': image_url,
                    'sku': line.product.stockrecords.first().partner_sku,
                    'course_key': getattr(line.product.attr, 'course_key', None),
                    'title': title,
                    'subject': subject,
                } for line in basket.lines.all()
            ],
        }
        if kwargs:
            expected_response.update(**kwargs)

        self.assertDictEqual(expected_response, response.json())

    def clear_message_utils(self):
        # The message_utils uses the request cache, so call this from setUp
        RequestCache.clear_all_namespaces()


@ddt.ddt
class PaymentApiViewTests(PaymentApiResponseTestMixin, BasketMixin, DiscoveryMockMixin,
                          EnterpriseServiceMockMixin, TestCase):
    """ PaymentApiViewTests basket api tests. """
    path = reverse('bff:payment:v0:payment')
    maxDiff = None

    def setUp(self):
        super(PaymentApiViewTests, self).setUp()
        self.clear_message_utils()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)
        self.course = CourseFactory(name='PaymentApiViewTests', partner=self.partner)
        responses.start()

    def tearDown(self):
        super().tearDown()
        responses.reset()

    def test_empty_basket(self):
        """ Verify empty basket is returned. """
        basket = self.create_empty_basket()
        self.assert_empty_basket_response(basket=basket)

    @ddt.data('verified', 'professional', 'credit')
    def test_seat_type(self, certificate_type):
        seat = self.create_seat(self.course, seat_price=100, cert_type=certificate_type)
        basket = self.create_basket_and_add_product(seat)
        self.mock_access_token_response()
        self.assertEqual(basket.lines.count(), 1)
        self.mock_course_run_detail_endpoint(
            self.course, discovery_api_url=self.site_configuration.discovery_api_url
        )

        with self.assert_events_fired_to_segment(basket):
            self.assert_expected_response(
                basket,
                certificate_type=certificate_type,
                image_url=u'/path/to/image.jpg',
                title=u'PaymentApiViewTests',
            )

    @override_settings(
        BRAZE_EVENT_REST_ENDPOINT='rest.braze.com',
        BRAZE_API_KEY='test-api-key',
    )
    def test_cart_viewed_event(self):
        """ Tests the basket added event is properly fired for a single seat """
        seat = self.create_seat(self.course)
        basket = self.create_basket_and_add_product(seat)
        self.mock_access_token_response()
        self.mock_course_run_detail_endpoint(self.course, discovery_api_url=self.site_configuration.discovery_api_url)
        braze_url = 'https://{url}/users/track'.format(url=getattr(settings, 'BRAZE_EVENT_REST_ENDPOINT'))
        responses.add(
            responses.POST, braze_url,
            json={'events_processed': 1, 'message': 'success'},
            content_type='application/json'
        )
        with mock.patch('ecommerce.extensions.basket.views.track_braze_event') as mock_track:
            self.assert_expected_response(
                basket,
                image_url='/path/to/image.jpg',
                title='PaymentApiViewTests',
            )
            mock_track.assert_called_with(self.user, 'edx.bi.ecommerce.cart.viewed', {
                'basket_discount': 0, 'basket_original_price': 100, 'basket_total': 100,
                'bundle_variant': None, 'currency': basket.currency, 'products': [
                    {'title': 'PaymentApiViewTests', 'image': '/path/to/image.jpg'}
                ], 'product_slug': None, 'product_subject': None, 'product_title': 'PaymentApiViewTests',
            })

    @override_settings(
        BRAZE_EVENT_REST_ENDPOINT='rest.braze.com',
        BRAZE_API_KEY='test-api-key',
    )
    @ddt.data(50, 100)
    def test_cart_viewed_event_with_discount(self, discount_value):
        """ Tests the basket added event correctly takes discounts into account """
        seat = self.create_seat(self.course)
        basket = self.create_basket_and_add_product(seat)
        voucher = self.create_and_apply_benefit_to_basket(basket, seat, Benefit.PERCENTAGE, discount_value)
        self.mock_access_token_response()
        self.mock_course_run_detail_endpoint(self.course, discovery_api_url=self.site_configuration.discovery_api_url)
        braze_url = 'https://{url}/users/track'.format(url=getattr(settings, 'BRAZE_EVENT_REST_ENDPOINT'))
        responses.add(
            responses.POST, braze_url,
            json={'events_processed': 1, 'message': 'success'},
            content_type='application/json'
        )

        with mock.patch('ecommerce.extensions.basket.views.track_braze_event') as mock_track:
            self.assert_expected_response(
                basket,
                discount_value=discount_value,
                discount_type=Benefit.PERCENTAGE,
                image_url='/path/to/image.jpg',
                title='PaymentApiViewTests',
                voucher=voucher,
            )
            mock_track.assert_called_with(self.user, 'edx.bi.ecommerce.cart.viewed', {
                'basket_discount': discount_value, 'basket_original_price': 100, 'basket_total': 100 - discount_value,
                'bundle_variant': None, 'currency': basket.currency, 'products': [
                    {'title': 'PaymentApiViewTests', 'image': '/path/to/image.jpg'},
                ], 'product_slug': None, 'product_subject': None, 'product_title': 'PaymentApiViewTests',
            })

    @override_settings(
        BRAZE_EVENT_REST_ENDPOINT='rest.braze.com',
        BRAZE_API_KEY='test-api-key',
    )
    @ddt.data(([1, 2], 'full_bundle'), ([1, 2, 3], 'partial_bundle'))
    @ddt.unpack
    def test_cart_viewed_event_with_bundle(self, program_courses, bundle_variant):
        """ Tests the basket added event is properly fired for a bundle """
        entitlement_1 = create_or_update_course_entitlement(
            'verified', 200, self.partner, 'fake-uuid-1', 'Entitlement 1')
        entitlement_2 = create_or_update_course_entitlement(
            'verified', 200, self.partner, 'fake-uuid-2', 'Entitlement 2')
        basket = self.create_basket_and_add_product(entitlement_1)
        basket.add_product(entitlement_2)
        summary_price = 400  # two entitlements * $200/entitlement
        # Setting bundle status. Would usually be handled by the added
        basket_attr_type, __ = BasketAttributeType.objects.get_or_create(name=BUNDLE)
        BasketAttribute.objects.update_or_create(
            basket=basket,
            attribute_type=basket_attr_type,
            value_text=TEST_BUNDLE_ID
        )
        # Copying code from create_and_apply_benefit_to_basket so it can take in multiple products
        discount_value = 10
        _range = factories.RangeFactory(products=[entitlement_1, entitlement_2])
        voucher, __ = prepare_voucher(_range=_range, benefit_type=Benefit.PERCENTAGE, benefit_value=discount_value)
        basket.vouchers.add(voucher)
        Applicator().apply(basket)
        basket_discount = float(basket.total_incl_tax_excl_discounts) * (float(discount_value) / 100)

        self.mock_access_token_response()
        self.mock_course_detail_endpoint(self.site_configuration.discovery_api_url, course_key='fake-uuid-1')
        self.mock_course_detail_endpoint(self.site_configuration.discovery_api_url, course_key='fake-uuid-2')
        braze_url = 'https://{url}/users/track'.format(url=getattr(settings, 'BRAZE_EVENT_REST_ENDPOINT'))
        responses.add(
            responses.POST, braze_url,
            json={'events_processed': 1, 'message': 'success'},
            content_type='application/json'
        )
        program_data = {
            # I know these aren't courses, but for the purposes of the test, we only check the length of
            # the list of courses so this is simpler
            'courses': program_courses,
            'marketing_slug': 'program-slug',
            'subjects': [{'slug': 'computer-science'}],
            'title': 'Program Title',
            'type_attrs': {'slug': 'professional-certificate'},
        }
        with mock.patch('ecommerce.extensions.basket.views.track_braze_event') as mock_track:
            with mock.patch('ecommerce.extensions.basket.views.get_program', return_value=program_data):
                self.assert_expected_response(
                    basket,
                    discount_value=discount_value,
                    discount_type=Benefit.PERCENTAGE,
                    image_url='/path/to/image.jpg',
                    title='edX Demo Course',
                    product_type='Course Entitlement',
                    summary_price=summary_price,
                    voucher=voucher,
                )
                mock_track.assert_called_with(self.user, 'edx.bi.ecommerce.cart.viewed', {
                    'basket_discount': basket_discount, 'basket_original_price': summary_price,
                    'basket_total': summary_price - basket_discount, 'bundle_variant': bundle_variant,
                    'currency': basket.currency, 'products': [
                        {'title': 'edX Demo Course', 'image': '/path/to/image.jpg'},
                        {'title': 'edX Demo Course', 'image': '/path/to/image.jpg'},
                    ], 'product_slug': program_data['type_attrs']['slug'] + '/' + program_data['marketing_slug'],
                    'product_subject': program_data['subjects'][0]['slug'], 'product_title': program_data['title']
                })

    def test_enrollment_code_type(self):
        course, __, enrollment_code = self.prepare_course_seat_and_enrollment_code(seat_price=100)
        basket = self.create_basket_and_add_product(enrollment_code)
        self.mock_course_runs_endpoint(self.site_configuration.discovery_api_url, course_run=course)

        expected_message = {
            'message_type': 'info',
            'code': 'single-enrollment-code-warning',
            'data': {
                'course_about_url': 'http://lms.testserver.fake/courses/{course_id}/about'.format(
                    course_id=course.id,
                )
            }
        }
        self.assert_expected_response(
            basket,
            product_type=u'Enrollment Code',
            show_coupon_form=False,
            messages=[expected_message],
            summary_quantity=1,
            summary_subtotal=100,
        )

    @ddt.data(50, 100)
    def test_discounted_seat_type(self, discount_value):
        seat = self.create_seat(self.course, seat_price=100)
        basket = self.create_basket_and_add_product(seat)
        voucher = self.create_and_apply_benefit_to_basket(basket, seat, Benefit.PERCENTAGE, discount_value)

        self.assert_expected_response(
            basket,
            discount_value=discount_value,
            discount_type=Benefit.PERCENTAGE,
            voucher=voucher,
        )

    @ddt.data(True, False)
    def test_enable_stripe_payment_processor_flag(self, enable_stripe_payment_processor):
        with override_flag(ENABLE_STRIPE_PAYMENT_PROCESSOR, active=enable_stripe_payment_processor):
            seat = self.create_seat(self.course)
            basket = self.create_basket_and_add_product(seat)
            response = self.client.get(self.path)
            self.assert_expected_response(
                basket,
                response=response,
                enable_stripe_payment_processor=enable_stripe_payment_processor,
            )

    @responses.activate
    def test_enterprise_free_basket_redirect(self):
        """
        Verify redirect to FreeCheckoutView when basket is free
        and an Enterprise-related offer is applied.
        """
        self.course_run.create_or_update_seat('verified', True, Decimal(10))
        self.create_basket_and_add_product(self.course_run.seat_products[0])
        enterprise_offer = self.prepare_enterprise_offer()

        opts = {
            'ec_uuid': str(enterprise_offer.condition.enterprise_customer_uuid),
            'course_id': self.course_run.seat_products[0].course_id,
            'username': self.user.username,
        }
        self.mock_consent_get(**opts)

        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['redirect'], absolute_url(self.request, 'checkout:free-checkout'))

    def test_failed_enterprise_consent_message(self):
        seat = self.create_seat(self.course)
        basket = self.create_basket_and_add_product(seat)

        params = 'consent_failed=THISISACOUPONCODE'

        url = '{path}?{params}'.format(
            path=self.get_full_url(self.path),
            params=params
        )
        expected_message = {
            'message_type': 'error',
            'user_message': u"Could not apply the code 'THISISACOUPONCODE'; it requires data sharing consent.",
        }
        self.assert_expected_response(
            basket,
            url=url,
            status_code=400,
            messages=[expected_message],
        )

    def test_segment_exception_log(self):
        self.verify_exception_logged_on_segment_error()

    @responses.activate
    def test_enterprise_offer_free_basket_redirect_to_dsc(self):
        """
        Verify redirect to Data Sharing Consent page if basket is free
        and an Enterprise-related offer is applied and Enterprise customer
        required the consent.
        """
        self.course_run.create_or_update_seat('verified', True, Decimal(10))
        self.create_basket_and_add_product(self.course_run.seat_products[0])
        enterprise_offer = self.prepare_enterprise_offer()

        opts = {
            'ec_uuid': str(enterprise_offer.condition.enterprise_customer_uuid),
            'course_id': self.course_run.seat_products[0].course_id,
            'username': self.user.username,
            'required': True
        }
        self.mock_consent_response(**opts)

        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)

        expected_redirect_url = construct_enterprise_course_consent_url(
            self.request,
            self.course_run.seat_products[0].course_id,
            str(enterprise_offer.condition.enterprise_customer_uuid)
        )
        self.assertEqual(response.data['redirect'], expected_redirect_url)

    def test_enterprise_offer_free_basket_with_wrong_basket(self):
        """
        Verify that we don't redirect to Data Sharing Consent page if basket is free
        and an Enterprise-related offer is applied but basket contains more than 1 products.
        """
        seat1 = self.create_seat(self.course, seat_price=100, cert_type='verified')
        seat2 = self.create_seat(self.course_run, seat_price=100, cert_type='verified')
        basket = self.create_basket_and_add_product(seat1)
        basket.add(seat2)
        offer = self.prepare_enterprise_offer()
        self.mock_catalog_contains_course_runs(
            [self.course_run.id, self.course.id],
            offer.condition.enterprise_customer_uuid,
            enterprise_customer_catalog_uuid=offer.condition.enterprise_customer_catalog_uuid,
        )
        self.mock_course_runs_endpoint(self.site_configuration.discovery_api_url, course_run=self.course)
        self.mock_course_runs_endpoint(self.site_configuration.discovery_api_url, course_run=self.course_run)

        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.data['redirect'], absolute_url(self.request, 'checkout:free-checkout'))


class VoucherAddMixin(LmsApiMockMixin, DiscoveryMockMixin):
    def setUp(self):
        super(VoucherAddMixin, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)
        self.basket = factories.BasketFactory(owner=self.user, site=self.site)

        # Fallback storage is needed in tests with messages
        self.request.user = self.user
        self.request.basket = self.basket
        responses.start()

    def tearDown(self):
        super().tearDown()
        responses.reset()

    def test_no_voucher_error_msg(self):
        product = ProductFactory()
        self.basket.add_product(product)
        messages = [{
            'message_type': u'error',
            'user_message': u"Coupon code '{code}' does not exist.".format(code=COUPON_CODE),
        }]
        self.assert_response(product=product, status_code=400, messages=messages)

    def test_voucher_already_in_basket_error_msg(self):
        voucher, product = prepare_voucher(code=COUPON_CODE)
        self.basket.vouchers.add(voucher)
        self.basket.add_product(product)

        messages = [{
            'message_type': u'error',
            'user_message': u"You have already added coupon code '{code}' to your basket.".format(code=COUPON_CODE),
        }]
        self.assert_response(
            product=product,
            status_code=400,
            messages=messages,
            discount_value=100,
            voucher=voucher,
        )

    def test_voucher_expired_error_msg(self):
        self.mock_access_token_response()
        self.mock_account_api(self.request, self.user.username, data={'is_active': True})
        end_datetime = datetime.datetime.now() - datetime.timedelta(days=1)
        start_datetime = datetime.datetime.now() - datetime.timedelta(days=2)
        __, product = prepare_voucher(code=COUPON_CODE, start_datetime=start_datetime, end_datetime=end_datetime)
        self.basket.add_product(product)

        messages = [{
            'message_type': u'error',
            'user_message': u"Coupon code 'COUPONTEST' has expired.",
        }]
        self.assert_response(product=product, status_code=400, messages=messages)

    def test_voucher_added_to_basket_msg(self):
        self.mock_access_token_response()
        self.mock_account_api(self.request, self.user.username, data={'is_active': True})
        voucher, product = prepare_voucher(code=COUPON_CODE)
        self.basket.add_product(product)

        messages = [{
            'message_type': 'info',
            'user_message': u"Coupon code 'COUPONTEST' added to basket.",
        }]
        self.assert_response(
            product=product,
            discount_value=100,
            voucher=voucher,
            messages=messages,
        )

    def test_voucher_used_error_msg(self):
        """ Verify correct error message is returned when voucher has been used (Single use). """
        self.mock_access_token_response()
        self.mock_account_api(self.request, self.user.username, data={'is_active': True})
        voucher, product = prepare_voucher(code=COUPON_CODE)
        self.basket.add_product(product)
        order = factories.OrderFactory()
        VoucherApplication.objects.create(voucher=voucher, user=self.user, order=order)
        messages = [{
            'message_type': u'error',
            'user_message': u"Coupon code '{code}' is not available. "
                            "This coupon has already been used".format(code=COUPON_CODE),
        }]
        self.assert_response(product=product, status_code=400, messages=messages)

    def test_voucher_has_no_discount_error_msg(self):
        """ Verify correct error message is returned when voucher has no discount. """
        self.mock_access_token_response()
        self.mock_account_api(self.request, self.user.username, data={'is_active': True})
        __, product = prepare_voucher(code=COUPON_CODE, benefit_value=0)
        self.basket.add_product(product)
        messages = [{
            'message_type': u'warning',
            'user_message': u'Basket does not qualify for coupon code {code}.'.format(code=COUPON_CODE),
        }]
        self.assert_response(product=product, status_code=200, messages=messages)

    def test_voucher_not_valid_for_bundle(self):
        """ Verify correct error message is returned when voucher is used against a bundle. """
        self.mock_access_token_response()
        self.mock_account_api(self.request, self.user.username, data={'is_active': True})
        voucher, product = prepare_voucher(code=COUPON_CODE, benefit_value=0)
        new_product = factories.ProductFactory(categories=[], stockrecords__partner__short_code='second')
        self.basket.add_product(product)
        self.basket.add_product(new_product)
        BasketAttributeType.objects.get_or_create(name=BUNDLE)
        BasketAttribute.objects.update_or_create(
            basket=self.basket,
            attribute_type=BasketAttributeType.objects.get(name=BUNDLE),
            value_text=TEST_BUNDLE_ID
        )
        messages = [{
            'message_type': u'error',
            'user_message': u"Coupon code '{code}' is not valid for this "
                            u"basket for a bundled purchase.".format(code=voucher.code),
        }]
        self.assert_response(product=product, status_code=400, messages=messages, summary_price=19.98)

    def test_multi_use_voucher_valid_for_bundle(self):
        """ Verify multi use coupon works when voucher is used against a bundle. """
        self.mock_access_token_response()
        self.mock_account_api(self.request, self.user.username, data={'is_active': True})
        voucher, product = prepare_voucher(code=COUPON_CODE, benefit_value=10, usage=Voucher.MULTI_USE)
        new_product = factories.ProductFactory(categories=[], stockrecords__partner__short_code='second')
        self.basket.add_product(product)
        self.basket.add_product(new_product)
        _set_basket_bundle_status(TEST_BUNDLE_ID, self.basket)
        messages = [{
            'message_type': u'info',
            'user_message': u"Coupon code '{code}' added to basket.".format(code=voucher.code),
        }]
        self.assert_response(
            product=product,
            status_code=200,
            messages=messages,
            summary_price=19.98,
            summary_discounts=0.99,
            discount_value=10,
            voucher=voucher,
        )

    def test_inactive_voucher(self):
        """ Verify the view alerts the user if the voucher is inactive. """
        self.mock_access_token_response()
        self.mock_account_api(self.request, self.user.username, data={'is_active': True})
        start_datetime = datetime.datetime.now() + datetime.timedelta(days=1)
        end_datetime = start_datetime + datetime.timedelta(days=2)
        voucher, product = prepare_voucher(code=COUPON_CODE, start_datetime=start_datetime, end_datetime=end_datetime)
        self.basket.add_product(product)
        messages = [{
            'message_type': u'error',
            'user_message': u"Coupon code '{code}' is not active.".format(code=voucher.code),
        }]
        self.assert_response(
            product=product,
            status_code=400,
            messages=messages,
        )

    @mock.patch('ecommerce.extensions.basket.views.get_enterprise_customer_from_voucher')
    def test_redirects_with_enterprise_customer(self, get_ec):
        """
        Test that when a coupon code is entered on the checkout page, and that coupon code is
        linked to an EnterpriseCustomer, the user is kicked over to the RedeemCoupon flow.
        """
        self.mock_access_token_response()
        self.mock_account_api(self.request, self.user.username, data={'is_active': True})
        get_ec.return_value = {'value': 'othervalue'}
        __, product = prepare_voucher(code=COUPON_CODE)
        self.basket.add_product(product)

        stock_record = Selector().strategy().fetch_for_product(product).stockrecord
        expected_redirect_url = (
            u'{coupons_redeem_base_url}?code=COUPONTEST&sku={sku}&'
            u'failure_url=http%3A%2F%2F{domain}%2Fbasket%2F%3Fconsent_failed%3D{code}'
        ).format(
            coupons_redeem_base_url=absolute_url(self.request, 'coupons:redeem'),
            sku=stock_record.partner_sku,
            code=COUPON_CODE,
            domain=self.site.domain,
        )
        self.assert_response_redirect(expected_redirect_url)

    def assert_account_activation_rendered(self):
        expected_redirect_url = absolute_url(self.request, 'offers:email_confirmation')
        self.assert_response_redirect(expected_redirect_url)

    def test_activation_required_for_inactive_user(self):
        self.mock_access_token_response()
        self.mock_account_api(self.request, self.user.username, data={'is_active': False})
        __, product = prepare_voucher(code=COUPON_CODE)
        self.basket.add_product(product)
        self.assert_account_activation_rendered()

    def test_activation_required_for_inactive_user_email_domain_offer(self):
        self.mock_access_token_response()
        self.mock_account_api(self.request, self.user.username, data={'is_active': False})
        self.site.siteconfiguration.require_account_activation = False
        self.site.siteconfiguration.save()
        email_domain = self.user.email.split('@')[1]
        __, product = prepare_voucher(code=COUPON_CODE, email_domains=email_domain)
        self.basket.add_product(product)
        self.assert_account_activation_rendered()

    def test_activation_not_required_for_inactive_user_when_disabled_for_site(self):
        self.mock_access_token_response()
        self.mock_account_api(self.request, self.user.username, data={'is_active': False})
        self.site.siteconfiguration.require_account_activation = False
        self.site.siteconfiguration.save()
        voucher, product = prepare_voucher(code=COUPON_CODE)
        self.basket.add_product(product)
        messages = [{
            'message_type': 'info',
            'user_message': f"Coupon code '{COUPON_CODE}' added to basket.",
        }]
        self.assert_response(
            product=product,
            discount_value=100,
            voucher=voucher,
            messages=messages,
        )

    def _get_account_activation_view_response(self, keys, template_name):
        url = '{url}?{params}'.format(
            url=reverse('offers:email_confirmation'),
            params=urllib.parse.urlencode([('course_id', key) for key in keys])
        )
        with self.assertTemplateUsed(template_name):
            return self.client.get(url)

    def _assert_account_activation_rendered(self, keys, expected_titles):
        """
        Assert the account activation view.
        """
        response = self._get_account_activation_view_response(keys, "edx/email_confirmation_required.html")
        expected_titles = expected_titles if isinstance(expected_titles, list) else [expected_titles]
        self.assertIn(u'An email has been sent to {}'.format(self.user.email), response.content.decode('utf-8'))
        for expected_title in expected_titles:
            self.assertIn(u'{}'.format(expected_title), response.content.decode('utf-8'))

    def test_account_activation_rendered(self):
        """
        Test the account activation view.
        """
        course = CourseFactory()
        other_course = CourseFactory()
        course_key = "course+key"

        # test single course_run
        self._assert_account_activation_rendered([course.id], course.name)

        # test multiple course_run
        self._assert_account_activation_rendered([course.id, other_course.id], [course.name, other_course.name])

        # test course key
        self.mock_access_token_response()
        self.mock_course_detail_endpoint(
            discovery_api_url=self.site_configuration.discovery_api_url,
            course_key=course_key
        )
        self._assert_account_activation_rendered([course_key], "edX Demo Course",)

    def test_account_activation_rendered_with_error(self):
        """
        Test the account activation view if exception raised..
        """
        course_key = "course+key"

        # test exception raise if discovery endpoint doesn't work as expected.
        self.mock_access_token_response()
        self.mock_course_detail_endpoint_error(
            course_key,
            discovery_api_url=self.site_configuration.discovery_api_url,
            error=ReqConnectionError,
        )
        response = self._get_account_activation_view_response([course_key], "404.html")
        self.assertIn(u'Not Found', response.content.decode('utf-8'))


class QuantityApiViewTests(PaymentApiResponseTestMixin, BasketMixin, DiscoveryMockMixin, TestCase):
    """ QuantityApiViewTests basket api tests. """
    path = reverse('bff:payment:v0:quantity')
    maxDiff = None

    def setUp(self):
        super(QuantityApiViewTests, self).setUp()
        self.clear_message_utils()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)
        self.course, self.seat, self.enrollment_code = self.prepare_course_seat_and_enrollment_code(seat_price=100)
        responses.start()

    def tearDown(self):
        super().tearDown()
        responses.reset()

    def prepare_enrollment_code_basket(self):
        basket = self.create_basket_and_add_product(self.enrollment_code)
        self.mock_course_runs_endpoint(self.site_configuration.discovery_api_url, course_run=self.course)
        return basket

    def test_response_success(self):
        """ Verify a successful response is returned. """
        basket = self.prepare_enrollment_code_basket()
        response = self.client.post(self.path, data={'quantity': 5})

        expected_message = {
            'message_type': 'info',
            'code': 'quantity-update-success-message',
        }
        self.assert_expected_response(
            basket,
            product_type=u'Enrollment Code',
            response=response,
            show_coupon_form=False,
            messages=[expected_message],
            order_total=500,
            summary_quantity=5,
            summary_subtotal=500,
        )

    def test_empty_basket_error(self):
        """ Verify empty basket error is returned. """
        basket = self.create_empty_basket()
        response = self.client.post(self.path, data={'quantity': 5})

        self.assert_empty_basket_response(
            basket=basket,
            response=response,
            status_code=400,
        )

    def test_response_validation_error(self):
        """ Verify a validation error is returned. """
        basket = self.prepare_enrollment_code_basket()
        response = self.client.post(self.path, data={'quantity': -1})

        expected_messages = [
            {
                'message_type': 'warning',
                'user_message': "Your basket couldn't be updated. Please correct any validation errors below.",
            },
            {
                'message_type': 'warning',
                'user_message': 'Ensure this value is greater than or equal to 0.',
            },
            {
                'message_type': 'info',
                'code': 'single-enrollment-code-warning',
                'data': {
                    'course_about_url': 'http://lms.testserver.fake/courses/{course_id}/about'.format(
                        course_id=self.course.id,
                    )
                }
            }
        ]
        self.assert_expected_response(
            basket,
            product_type=u'Enrollment Code',
            response=response,
            show_coupon_form=False,
            status_code=400,
            messages=expected_messages,
            summary_quantity=1,
            summary_subtotal=100,
        )

    def test_with_seat_product(self):
        """ Verify that basket error is returned for seat product
        and quantity is not updated. """
        basket = self.create_basket_and_add_product(self.seat)
        response = self.client.post(self.path, data={'quantity': 2})

        self.assert_expected_response(
            basket,
            product_type=u'Seat',
            response=response,
            show_coupon_form=True,
            status_code=400,
        )


class VoucherAddApiViewTests(PaymentApiResponseTestMixin, VoucherAddMixin, TestCase):
    """ VoucherAddApiViewTests basket api tests. """
    path = reverse('bff:payment:v0:addvoucher')
    maxDiff = None

    def setUp(self):
        super(VoucherAddApiViewTests, self).setUp()
        self.clear_message_utils()

    def assert_response(self, product, summary_price=9.99, **kwargs):
        response = self._get_response()
        self.assert_expected_response(
            self.basket,
            response=response,
            title=product.title,
            certificate_type=None,
            product_type=product.get_product_class().name,
            currency=u'GBP',
            summary_price=summary_price,
            discount_type=Benefit.PERCENTAGE,
            **kwargs
        )

    def assert_response_redirect(self, expected_redirect_url):
        response = self._get_response()
        self.assertEqual(response.data['redirect'], expected_redirect_url)

    def _get_response(self):
        return self.client.post(self.path, {'code': COUPON_CODE})

    def test_empty_basket_error(self):
        """ Verify empty basket error is returned. """
        response = self._get_response()

        self.assert_empty_basket_response(
            basket=self.basket,
            response=response,
            status_code=400,
        )


class VoucherRemoveApiViewTests(PaymentApiResponseTestMixin, TestCase):
    """ VoucherRemoveApiViewTests basket api tests. """
    maxDiff = None

    def setUp(self):
        super(VoucherRemoveApiViewTests, self).setUp()
        self.clear_message_utils()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)
        responses.start()

    def tearDown(self):
        super().tearDown()
        responses.reset()

    def test_response_success(self):
        """ Verify a successful response is returned. """
        self.mock_access_token_response()
        voucher, product = prepare_voucher(code=COUPON_CODE)
        basket = factories.BasketFactory(owner=self.user, site=self.site)
        basket.add_product(product)
        valid, _ = apply_voucher_on_basket_and_check_discount(voucher, self.request, basket)
        self.assertTrue(valid)

        path = reverse('bff:payment:v0:payment')
        response = self.client.get(path)
        self.assert_expected_response(
            basket,
            response=response,
            currency=u'GBP',
            certificate_type=None,
            voucher=voucher,
            title=product.title,
            product_type=product.get_product_class().name,
            discount_value=100,
            discount_type=Benefit.PERCENTAGE,
            summary_price=9.99,
        )

        path = reverse('bff:payment:v0:removevoucher', kwargs={'voucherid': voucher.id})
        response = self.client.delete(path)

        messages = [{
            'message_type': u'info',
            'user_message': u"Coupon code '{code}' was removed from your basket.".format(code=voucher.code),
        }]
        self.assert_expected_response(
            basket,
            response=response,
            currency=u'GBP',
            certificate_type=None,
            voucher=voucher,
            title=product.title,
            product_type=product.get_product_class().name,
            summary_price=9.99,
            messages=messages,
        )

    def test_empty_basket_error(self):
        """ Verify empty basket error is returned. """
        basket = self.create_empty_basket()

        path = reverse('bff:payment:v0:removevoucher', kwargs={'voucherid': 1})
        response = self.client.delete(path)

        messages = [{
            'message_type': 'error',
            'user_message': "No coupon found with id '1'"
        }]
        self.assert_empty_basket_response(
            basket=basket,
            response=response,
            messages=messages,
            status_code=400,
        )
