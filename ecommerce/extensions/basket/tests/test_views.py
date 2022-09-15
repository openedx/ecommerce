import datetime
import itertools
import urllib.error
import urllib.parse
from contextlib import contextmanager
from decimal import Decimal

import ddt
import mock
import pytz
import responses
from django.conf import settings
from django.contrib.messages import get_messages
from django.http import HttpResponseRedirect
from django.test import override_settings
from django.urls import reverse
from edx_django_utils.cache import RequestCache, TieredCache
from oscar.apps.basket.forms import BasketVoucherForm
from oscar.core.loading import get_class, get_model
from oscar.test import factories
from requests.exceptions import ConnectionError as ReqConnectionError
from requests.exceptions import RequestException, Timeout
from testfixtures import LogCapture
from waffle.testutils import override_flag

from ecommerce.core.exceptions import SiteConfigurationError
from ecommerce.core.tests import toggle_switch
from ecommerce.core.url_utils import absolute_url, get_lms_url
from ecommerce.core.utils import get_cache_key
from ecommerce.coupons.tests.mixins import CouponMixin, DiscoveryMockMixin
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.enterprise.tests.mixins import EnterpriseServiceMockMixin
from ecommerce.enterprise.utils import construct_enterprise_course_consent_url
from ecommerce.entitlements.utils import create_or_update_course_entitlement
from ecommerce.extensions.analytics.utils import translate_basket_line_for_segment
from ecommerce.extensions.basket.constants import EMAIL_OPT_IN_ATTRIBUTE, ENABLE_STRIPE_PAYMENT_PROCESSOR
from ecommerce.extensions.basket.tests.mixins import BasketMixin
from ecommerce.extensions.basket.tests.test_utils import TEST_BUNDLE_ID
from ecommerce.extensions.basket.utils import _set_basket_bundle_status, apply_voucher_on_basket_and_check_discount
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.extensions.offer.constants import DYNAMIC_DISCOUNT_FLAG
from ecommerce.extensions.offer.utils import format_benefit_value
from ecommerce.extensions.order.utils import UserAlreadyPlacedOrder
from ecommerce.extensions.payment.constants import CLIENT_SIDE_CHECKOUT_FLAG_NAME
from ecommerce.extensions.payment.forms import PaymentForm
from ecommerce.extensions.payment.tests.processors import DummyProcessor
from ecommerce.extensions.test.factories import create_order, prepare_voucher
from ecommerce.tests.factories import ProductFactory, SiteConfigurationFactory, StockRecordFactory
from ecommerce.tests.mixins import ApiMockMixin, LmsApiMockMixin
from ecommerce.tests.testcases import TestCase

Applicator = get_class('offer.applicator', 'Applicator')
Basket = get_model('basket', 'Basket')
BasketAttribute = get_model('basket', 'BasketAttribute')
BasketAttributeType = get_model('basket', 'BasketAttributeType')
Benefit = get_model('offer', 'Benefit')
Catalog = get_model('catalogue', 'Catalog')
Condition = get_model('offer', 'Condition')
ConditionalOffer = get_model('offer', 'ConditionalOffer')
OrderLine = get_model('order', 'Line')
Product = get_model('catalogue', 'Product')
ProductAttribute = get_model('catalogue', 'ProductAttribute')
Selector = get_class('partner.strategy', 'Selector')
StockRecord = get_model('partner', 'StockRecord')
Voucher = get_model('voucher', 'Voucher')
VoucherAddView = get_class('basket.views', 'VoucherAddView')
VoucherApplication = get_model('voucher', 'VoucherApplication')

COUPON_CODE = 'COUPONTEST'
BUNDLE = 'bundle_identifier'


@ddt.ddt
class BasketAddItemsViewTests(CouponMixin, DiscoveryTestMixin, DiscoveryMockMixin, LmsApiMockMixin, BasketMixin,
                              EnterpriseServiceMockMixin, TestCase):
    """ BasketAddItemsView view tests. """
    path = reverse('basket:basket-add')

    def setUp(self):
        super(BasketAddItemsViewTests, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)

        self.course = CourseFactory(partner=self.partner)
        product = self.course.create_or_update_seat('verified', False, 50)
        self.stock_record = StockRecordFactory(product=product, partner=self.partner)
        self.catalog = Catalog.objects.create(partner=self.partner)
        self.catalog.stock_records.add(self.stock_record)

    def _get_response(self, product_skus, **url_params):
        qs = urllib.parse.urlencode({'sku': product_skus}, True)
        url = '{root}?{qs}'.format(root=self.path, qs=qs)
        for name, value in url_params.items():
            url += '&{}={}'.format(name, value)
        return self.client.get(url)

    def test_add_multiple_products_to_basket(self):
        """ Verify the basket accepts multiple products. """
        products = ProductFactory.create_batch(3, stockrecords__partner=self.partner)
        response = self._get_response([product.stockrecords.first().partner_sku for product in products])
        self.assertEqual(response.status_code, 303)

        basket = response.wsgi_request.basket
        self.assertEqual(basket.status, Basket.OPEN)
        self.assertEqual(basket.lines.count(), len(products))

    def test_basket_with_utm_params(self):
        """ Verify the basket includes utm params after redirect. """
        products = ProductFactory.create_batch(3, stockrecords__partner=self.partner)
        response = self._get_response(
            [product.stockrecords.first().partner_sku for product in products],
            utm_source='test',
        )
        expected_url = self.get_full_url(reverse('basket:summary')) + '?utm_source=test'
        self.assertEqual(response.url, expected_url)

    @responses.activate
    def test_redirect_to_basket_summary(self):
        """
        Verify the view redirects to the basket summary page, and that the user's basket is prepared for checkout.
        """
        self.create_coupon(catalog=self.catalog, code=COUPON_CODE, benefit_value=5)

        self.mock_course_runs_endpoint(self.site_configuration.discovery_api_url, course_run=self.course)
        response = self._get_response(self.stock_record.partner_sku, code=COUPON_CODE)
        expected_url = self.get_full_url(reverse('basket:summary'))
        self.assertRedirects(response, expected_url, status_code=303)

        basket = Basket.objects.get(owner=self.user, site=self.site)
        self.assertEqual(basket.status, Basket.OPEN)
        self.assertEqual(basket.lines.count(), 1)
        self.assertTrue(basket.contains_a_voucher)
        self.assertEqual(basket.lines.first().product, self.stock_record.product)

    @ddt.data(*itertools.product((True, False), (True, False)))
    @ddt.unpack
    def test_microfrontend_for_single_course_purchase_if_configured(self, enable_redirect, set_url):
        microfrontend_url = self.configure_redirect_to_microfrontend(enable_redirect, set_url)
        response = self._get_response(self.stock_record.partner_sku, utm_source='test')

        expect_microfrontend = enable_redirect and set_url
        expected_url = microfrontend_url if expect_microfrontend else self.get_full_url(reverse('basket:summary'))
        expected_url += '?utm_source=test'
        self.assertRedirects(response, expected_url, status_code=303, fetch_redirect_response=False)

    def test_add_invalid_code_to_basket(self):
        """
        When the BasketAddItemsView receives an invalid code as a parameter, add a message to the url.
        This message will be displayed on the payment page.
        """
        microfrontend_url = self.configure_redirect_to_microfrontend(True, True)
        response = self._get_response(self.stock_record.partner_sku, code='invalidcode')
        expected_url = microfrontend_url + '?error_message=Code%20invalidcode%20is%20invalid.'
        self.assertRedirects(response, expected_url, status_code=303, fetch_redirect_response=False)

    @responses.activate
    def test_microfrontend_for_enrollment_code_seat(self):
        microfrontend_url = self.configure_redirect_to_microfrontend()

        course, __, enrollment_code = self.prepare_course_seat_and_enrollment_code()
        basket = factories.BasketFactory(owner=self.user, site=self.site)
        basket.add_product(enrollment_code, 1)
        self.mock_course_runs_endpoint(self.site_configuration.discovery_api_url, course_run=course)

        response = self._get_response(enrollment_code.stockrecords.first().partner_sku)
        self.assertRedirects(response, microfrontend_url, status_code=303, fetch_redirect_response=False)

    def test_add_multiple_products_no_skus_provided(self):
        """ Verify the Bad request exception is thrown when no skus are provided. """
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content.decode('utf-8'), 'No SKUs provided.')

    def test_add_multiple_products_no_available_products(self):
        """ Verify the Bad request exception is thrown when no skus are provided. """
        response = self.client.get(self.path, data=[('sku', 1), ('sku', 2)])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content.decode('utf-8'), 'Products with SKU(s) [1, 2] do not exist.')

    @ddt.data(Voucher.SINGLE_USE, Voucher.MULTI_USE)
    def test_add_multiple_products_and_use_voucher(self, usage):
        """ Verify the basket accepts multiple products and a single use voucher. """
        products = ProductFactory.create_batch(3, stockrecords__partner=self.partner)
        product_range = factories.RangeFactory(products=products)
        voucher, __ = prepare_voucher(_range=product_range, usage=usage)

        response = self._get_response(
            [product.stockrecords.first().partner_sku for product in products],
            code=voucher.code,
        )
        self.assertEqual(response.status_code, 303)
        basket = response.wsgi_request.basket
        self.assertEqual(basket.status, Basket.OPEN)
        self.assertTrue(basket.contains_voucher(voucher.code))

    def test_all_already_purchased_products(self):
        """
        Test user can not purchase products again using the multiple item view
        """
        course = CourseFactory(partner=self.partner)
        product1 = course.create_or_update_seat("Verified", True, 0)
        product2 = course.create_or_update_seat("Professional", True, 0)
        stock_record = StockRecordFactory(product=product1, partner=self.partner)
        catalog = Catalog.objects.create(partner=self.partner)
        catalog.stock_records.add(stock_record)
        stock_record = StockRecordFactory(product=product2, partner=self.partner)
        catalog.stock_records.add(stock_record)

        with mock.patch.object(UserAlreadyPlacedOrder, 'user_already_placed_order', return_value=True):
            response = self._get_response(
                [product.stockrecords.first().partner_sku for product in [product1, product2]],
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['error'], 'You have already purchased these products')

    def test_not_already_purchased_products(self):
        """
        Test user can purchase products which have not been already purchased
        """
        products = ProductFactory.create_batch(3, stockrecords__partner=self.partner)
        with mock.patch.object(UserAlreadyPlacedOrder, 'user_already_placed_order', return_value=False):
            response = self._get_response([product.stockrecords.first().partner_sku for product in products])
            self.assertEqual(response.status_code, 303)

    def test_one_already_purchased_product(self):
        """
        Test prepare_basket removes already purchased product and checkout for the rest of products
        """
        order = create_order(site=self.site, user=self.user)
        products = ProductFactory.create_batch(3, stockrecords__partner=self.partner)
        products.append(OrderLine.objects.get(order=order).product)
        response = self._get_response([product.stockrecords.first().partner_sku for product in products])
        basket = response.wsgi_request.basket
        self.assertEqual(response.status_code, 303)
        self.assertEqual(basket.lines.count(), len(products) - 1)

    def test_no_available_product(self):
        """ The view should return HTTP 400 if the product is not available for purchase. """
        product = self.stock_record.product
        product.expires = pytz.utc.localize(datetime.datetime.min)
        product.save()
        self.assertFalse(Selector().strategy().fetch_for_product(product).availability.is_available_to_buy)

        expected_content = 'No product is available to buy.'
        response = self._get_response(self.stock_record.partner_sku)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content.decode('utf-8'), expected_content)

    def test_with_both_unavailable_and_available_products(self):
        """ Verify the basket ignores unavailable products and continue with available products. """
        products = ProductFactory.create_batch(3, stockrecords__partner=self.partner)

        products[0].expires = pytz.utc.localize(datetime.datetime.min)
        products[0].save()
        self.assertFalse(Selector().strategy().fetch_for_product(products[0]).availability.is_available_to_buy)

        response = self._get_response([product.stockrecords.first().partner_sku for product in products])
        self.assertEqual(response.status_code, 303)
        basket = response.wsgi_request.basket
        self.assertEqual(basket.status, Basket.OPEN)

    @ddt.data(
        ('false', 'False'),
        ('true', 'True'),
    )
    @ddt.unpack
    def test_email_opt_in_when_explicitly_given(self, opt_in, expected_value):
        """
        Verify the email_opt_in query string is saved into a BasketAttribute.
        """
        response = self._get_response(self.stock_record.partner_sku, email_opt_in=opt_in)
        basket = response.wsgi_request.basket
        basket_attribute = BasketAttribute.objects.get(
            basket=basket,
            attribute_type=BasketAttributeType.objects.get(name=EMAIL_OPT_IN_ATTRIBUTE),
        )
        self.assertEqual(basket_attribute.value_text, expected_value)

    def test_email_opt_in_when_not_given(self):
        """
        Verify that email_opt_in defaults to false if not specified.
        """
        response = self._get_response(self.stock_record.partner_sku)
        basket = response.wsgi_request.basket
        basket_attribute = BasketAttribute.objects.get(
            basket=basket,
            attribute_type=BasketAttributeType.objects.get(name=EMAIL_OPT_IN_ATTRIBUTE),
        )
        self.assertEqual(basket_attribute.value_text, 'False')

    @responses.activate
    def test_enterprise_free_basket_redirect(self):
        """
        Verify redirect to FreeCheckoutView when basket is free
        and an Enterprise-related offer is applied.
        """
        enterprise_offer = self.prepare_enterprise_offer()

        self.mock_catalog_contains_course_runs(
            [self.course.id],
            enterprise_offer.condition.enterprise_customer_uuid,
            enterprise_customer_catalog_uuid=enterprise_offer.condition.enterprise_customer_catalog_uuid,
        )

        opts = {
            'ec_uuid': str(enterprise_offer.condition.enterprise_customer_uuid),
            'course_id': self.course.id,
            'username': self.user.username,
        }
        self.mock_consent_get(**opts)

        response = self._get_response(self.stock_record.partner_sku)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, absolute_url(self.request, 'checkout:free-checkout'))


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


@ddt.ddt
class BasketSummaryViewTests(EnterpriseServiceMockMixin, DiscoveryTestMixin, DiscoveryMockMixin, LmsApiMockMixin,
                             ApiMockMixin, BasketMixin, BasketLogicTestMixin, TestCase):
    """ BasketSummaryView basket view tests. """
    path = reverse('basket:summary')

    def setUp(self):
        super(BasketSummaryViewTests, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)
        self.course = CourseFactory(name='BasketSummaryTest', partner=self.partner)
        site_configuration = self.site.siteconfiguration

        site_configuration.payment_processors = DummyProcessor.NAME
        site_configuration.client_side_payment_processor = DummyProcessor.NAME
        site_configuration.save()

        toggle_switch(settings.PAYMENT_PROCESSOR_SWITCH_PREFIX + DummyProcessor.NAME, True)
        responses.start()

    def tearDown(self):
        super().tearDown()
        responses.reset()

    @ddt.data(ReqConnectionError, RequestException, Timeout)
    def test_course_api_failure(self, error):
        """ Verify a connection error and timeout are logged when they happen. """
        seat = self.create_seat(self.course)
        basket = self.create_basket_and_add_product(seat)
        self.assertEqual(basket.lines.count(), 1)

        logger_name = 'ecommerce.extensions.basket.views'
        self.mock_api_error(
            error=error,
            url=get_lms_url('api/courses/v1/courses/{}/'.format(self.course.id))
        )

        with LogCapture(logger_name) as logger:
            response = self.client.get(self.path)
            self.assertEqual(response.status_code, 200)
            logger.check(
                (
                    logger_name, 'ERROR',
                    u'Failed to retrieve data from Discovery Service for course [{}].'.format(self.course.id)
                )
            )

    def test_non_seat_product(self):
        """Verify the basket accepts non-seat product types."""
        title = 'Test Product 123'
        description = 'All hail the test product.'
        product = factories.ProductFactory(title=title, description=description)
        self.create_basket_and_add_product(product)

        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        line_data = response.context['formset_lines_data'][0][1]
        self.assertEqual(line_data['product_title'], title)
        self.assertEqual(line_data['product_description'], description)

    def test_enrollment_code_seat_type(self):
        """Verify the correct seat type attribute is retrieved."""
        course, __, enrollment_code = self.prepare_course_seat_and_enrollment_code()
        self.create_basket_and_add_product(enrollment_code)
        self.mock_course_runs_endpoint(self.site_configuration.discovery_api_url, course_run=course)

        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['show_voucher_form'])
        line_data = response.context['formset_lines_data'][0][1]
        self.assertEqual(line_data['seat_type'], enrollment_code.attr.seat_type.capitalize())

    def test_microfrontend_for_single_course_purchase(self):
        microfrontend_url = self.configure_redirect_to_microfrontend()

        seat = self.create_seat(self.course)
        self.create_basket_and_add_product(seat)
        response = self.client.get(self.path)
        self.assertRedirects(response, microfrontend_url, status_code=302, fetch_redirect_response=False)

    def test_microfrontend_with_consent_failed_param(self):
        microfrontend_url = self.configure_redirect_to_microfrontend()

        params = 'consent_failed=THISISACOUPONCODE'
        url = '{}?{}'.format(self.path, params)
        response = self.client.get(url)
        expected_redirect_url = '{}?{}'.format(microfrontend_url, params)
        self.assertRedirects(response, expected_redirect_url, status_code=302, fetch_redirect_response=False)

    def test_microfrontend_for_enrollment_code_seat_type(self):
        microfrontend_url = self.configure_redirect_to_microfrontend()

        course, __, enrollment_code = self.prepare_course_seat_and_enrollment_code()
        self.create_basket_and_add_product(enrollment_code)
        self.mock_course_runs_endpoint(self.site_configuration.discovery_api_url, course_run=course)
        response = self.client.get(self.path)
        self.assertRedirects(response, microfrontend_url, status_code=302, fetch_redirect_response=False)

    @ddt.data(
        (Benefit.PERCENTAGE, 100),
        (Benefit.PERCENTAGE, 50),
        (Benefit.FIXED, 50)
    )
    @ddt.unpack
    @override_settings(PAYMENT_PROCESSORS=['ecommerce.extensions.payment.tests.processors.DummyProcessor'])
    def test_response_success(self, benefit_type, benefit_value):
        """ Verify a successful response is returned. """
        seat = self.create_seat(self.course, 500)
        basket = self.create_basket_and_add_product(seat)
        self.mock_access_token_response()
        self.create_and_apply_benefit_to_basket(basket, seat, benefit_type, benefit_value)

        self.assertEqual(basket.lines.count(), 1)
        self.mock_course_run_detail_endpoint(
            self.course, discovery_api_url=self.site_configuration.discovery_api_url
        )

        benefit, __ = Benefit.objects.get_or_create(type=benefit_type, value=benefit_value)
        with self.assert_events_fired_to_segment(basket):
            response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(len(response.context['formset_lines_data']), 1)

        line_data = response.context['formset_lines_data'][0][1]
        self.assertEqual(line_data['benefit_value'], format_benefit_value(benefit))
        self.assertEqual(line_data['seat_type'], seat.attr.certificate_type.capitalize())
        self.assertEqual(line_data['product_title'], self.course.name)
        self.assertFalse(line_data['enrollment_code'])
        self.assertEqual(response.context['payment_processors'][0].NAME, DummyProcessor.NAME)

    def test_track_segment_event_exception(self):
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

    def assert_empty_basket(self):
        """ Assert that the basket is empty on visiting the basket summary page. """
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['formset_lines_data'], [])
        self.assertEqual(response.context['total_benefit'], None)

    def test_no_basket_response(self):
        """ Verify there are no form, line and benefit data in the context for a non-existing basket. """
        self.assert_empty_basket()

    def test_line_item_discount_data(self):
        """ Verify that line item has correct discount data. """
        self.mock_course_runs_endpoint(self.site_configuration.discovery_api_url, course_run=self.course)
        seat = self.create_seat(self.course)
        basket = self.create_basket_and_add_product(seat)
        self.create_and_apply_benefit_to_basket(basket, seat, Benefit.PERCENTAGE, 50)

        course_without_benefit = CourseFactory()
        seat_without_benefit = self.create_seat(course_without_benefit)
        basket.add_product(seat_without_benefit, 1)

        response = self.client.get(self.path)
        lines = response.context['formset_lines_data']
        self.assertEqual(lines[0][1]['benefit_value'], '50%')
        self.assertEqual(lines[1][1]['benefit_value'], None)

    @mock.patch('ecommerce.extensions.offer.dynamic_conditional_offer.get_decoded_jwt_discount_from_request')
    @ddt.data(
        {'discount_percent': 15, 'discount_applicable': True},
        {'discount_percent': 15, 'discount_applicable': False},
        None)
    @override_flag(DYNAMIC_DISCOUNT_FLAG, active=True)
    def test_line_item_discount_data_dynamic_discount(self, discount_json, mock_get_discount):
        """ Verify that line item has correct discount data. """
        mock_get_discount.return_value = discount_json

        self.mock_course_runs_endpoint(self.site_configuration.discovery_api_url, course_run=self.course)
        seat = self.create_seat(self.course)
        basket = self.create_basket_and_add_product(seat)
        Applicator().apply(basket)

        response = self.client.get(self.path)
        lines = response.context['formset_lines_data']
        if discount_json and discount_json['discount_applicable']:
            self.assertEqual(
                lines[0][1]['line'].discount_value,
                discount_json['discount_percent'] / Decimal('100') * lines[0][1]['line'].price_incl_tax)
        else:
            self.assertEqual(
                lines[0][1]['line'].discount_value,
                Decimal(0))

    def test_cached_course(self):
        """ Verify that the course info is cached. """
        seat = self.create_seat(self.course, 50)
        basket = self.create_basket_and_add_product(seat)
        self.mock_access_token_response()
        self.assertEqual(basket.lines.count(), 1)
        self.mock_course_run_detail_endpoint(
            self.course, discovery_api_url=self.site_configuration.discovery_api_url
        )

        cache_key = get_cache_key(
            site_domain=self.site,
            resource="{}-{}".format('course_runs', self.course.id)
        )
        course_before_cached_response = TieredCache.get_cached_response(cache_key)
        self.assertFalse(course_before_cached_response.is_found)

        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        course_after_cached_response = TieredCache.get_cached_response(cache_key)
        self.assertEqual(course_after_cached_response.value['title'], self.course.name)

    @ddt.data({
        'course': 'edX+DemoX',
        'short_description': None,
        'title': 'Junk',
        'start': '2013-02-05T05:00:00Z',
    }, {
        'course': 'edX+DemoX',
        'short_description': None,
    })
    def test_empty_catalog_api_response(self, course_info):
        """ Check to see if we can handle empty response from the catalog api """
        seat = self.create_seat(self.course)
        self.create_basket_and_add_product(seat)
        self.mock_access_token_response()
        self.mock_course_run_detail_endpoint(
            self.course, self.site_configuration.discovery_api_url, course_info
        )
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        line_data = response.context['formset_lines_data'][0][1]
        self.assertEqual(line_data.get('image_url'), None)
        self.assertEqual(line_data.get('course_short_description'), None)

    def assert_order_details_in_context(self, product):
        """Assert order details message is in basket context for passed product."""
        self.create_basket_and_add_product(product)
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.context['order_details_msg'])

    @ddt.data(True, False)
    def test_order_details_msg(self, id_verification):
        """Verify the order details message is displayed for seats and enrollment codes."""
        __, seat, enrollment_code = self.prepare_course_seat_and_enrollment_code(
            seat_type='professional', id_verification=id_verification
        )
        self.assert_order_details_in_context(seat)
        self.assert_order_details_in_context(enrollment_code)

    @override_flag(CLIENT_SIDE_CHECKOUT_FLAG_NAME, active=True)
    @override_settings(PAYMENT_PROCESSORS=['ecommerce.extensions.payment.tests.processors.DummyProcessor'])
    def test_client_side_checkout(self):
        """ Verify the view returns the data necessary to initiate client-side checkout. """
        seat = self.create_seat(self.course)
        basket = self.create_basket_and_add_product(seat)

        response = self.client.get(self.get_full_url(self.path))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['enable_client_side_checkout'])

        actual_processor = response.context['client_side_payment_processor']
        self.assertIsInstance(actual_processor, DummyProcessor)

        payment_form = response.context['payment_form']
        self.assertIsInstance(payment_form, PaymentForm)
        self.assertEqual(payment_form.initial['basket'], basket)

    @override_flag(CLIENT_SIDE_CHECKOUT_FLAG_NAME, active=True)
    def test_client_side_checkout_with_invalid_configuration(self):
        """ Verify an error is raised if a payment processor is defined as the client-side processor,
        but is not active in the system."""
        self.site.siteconfiguration.client_side_payment_processor = 'blah'
        self.site.siteconfiguration.save()

        seat = self.create_seat(self.course)
        self.create_basket_and_add_product(seat)

        with self.assertRaises(SiteConfigurationError):
            self.client.get(self.get_full_url(self.path))

    def test_login_required_basket_summary(self):
        """ The view should redirect to the login page if the user is not logged in. """
        self.client.logout()
        response = self.client.get(self.path)
        expected_url = '{path}?next={next}'.format(path=reverse(settings.LOGIN_URL),
                                                   next=urllib.parse.quote(self.path))
        self.assertRedirects(response, expected_url, target_status_code=302)

    @ddt.data(
        (None, None),
        ('invalid-date', None),
        ('2017-02-01T00:00:00', datetime.datetime(2017, 2, 1)),
    )
    @ddt.unpack
    @override_settings(PAYMENT_PROCESSORS=['ecommerce.extensions.payment.tests.processors.DummyProcessor'])
    def test_context_data_contains_course_dates(self, date_string, expected_result):
        seat = self.create_seat(self.course)
        self.mock_access_token_response()
        self.create_basket_and_add_product(seat)
        self.mock_course_run_detail_endpoint(
            self.course,
            self.site_configuration.discovery_api_url,
            {
                'start': date_string,
                'end': date_string
            }
        )
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        for _, line_data in response.context['formset_lines_data']:
            self.assertEqual(line_data['course_start'], expected_result)
            self.assertEqual(line_data['course_end'], expected_result)

    def test_course_about_url(self):
        """
        Test that in case of bulk enrollment, We have the marketing url from course metadata
        if present in response.
        """
        course_run_info = {
            "course": "edX+DemoX",
            "title": 'course title here',
            "short_description": 'Foo',
            "start": "2013-02-05T05:00:00Z",
            "image": {
                "src": "/path/to/image.jpg",
            },
            'enrollment_end': None,
            'marketing_url': '/path/to/marketing/site'
        }
        self.mock_access_token_response()
        course, __, enrollment_code = self.prepare_course_seat_and_enrollment_code()
        self.create_basket_and_add_product(enrollment_code)
        self.mock_course_run_detail_endpoint(
            course,
            self.site_configuration.discovery_api_url,
            course_run_info
        )

        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        messages = list(response.context['messages'])
        self.assertEqual(len(messages), 1)
        self.assertContains(response, '/path/to/marketing/site', status_code=200)

    def test_failed_enterprise_consent_sends_message(self):
        """
        Test that if we receive an indication via a query parameter that data sharing
        consent was attempted, but failed, we send a message indicating such.
        """
        seat = self.create_seat(self.course)
        self.create_basket_and_add_product(seat)

        params = 'consent_failed=THISISACOUPONCODE'

        url = '{path}?{params}'.format(
            path=self.get_full_url(self.path),
            params=params
        )
        response = self.client.get(url)
        message = list(response.context['messages'])[0]

        self.assertEqual(
            str(message),
            'Could not apply the code \'THISISACOUPONCODE\'; it requires data sharing consent.'
        )

    @responses.activate
    def test_enterprise_free_basket_redirect(self):
        self.course_run.create_or_update_seat('verified', True, Decimal(100))
        self.create_basket_and_add_product(self.course_run.seat_products[0])
        enterprise_offer = self.prepare_enterprise_offer(enterprise_customer_name='Foo Enterprise')

        opts = {
            'ec_uuid': str(enterprise_offer.condition.enterprise_customer_uuid),
            'course_id': self.course_run.seat_products[0].course_id,
            'username': self.user.username,
        }
        self.mock_consent_get(**opts)

        response = self.client.get(self.path)
        self.assertRedirects(
            response,
            absolute_url(self.request, 'checkout:free-checkout'),
            fetch_redirect_response=False,
        )

    @override_settings(PAYMENT_PROCESSORS=['ecommerce.extensions.payment.tests.processors.DummyProcessor'])
    @ddt.data(100, 50)
    def test_discounted_free_basket(self, percentage_benefit):
        seat = self.create_seat(self.course, seat_price=100)
        basket = self.create_basket_and_add_product(seat)
        self.mock_access_token_response()
        self.mock_course_run_detail_endpoint(
            self.course, discovery_api_url=self.site_configuration.discovery_api_url
        )

        self.create_and_apply_benefit_to_basket(basket, seat, Benefit.PERCENTAGE, percentage_benefit)

        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['free_basket'], percentage_benefit == 100)


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
            'user_message': u"Coupon code '{code}' added to basket.".format(code=COUPON_CODE),
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


class VoucherAddViewTests(VoucherAddMixin, TestCase):
    """ Tests for VoucherAddView. """

    def setUp(self):
        super(VoucherAddViewTests, self).setUp()
        self.view = VoucherAddView()
        self.view.request = self.request

        self.form = BasketVoucherForm()
        self.form.cleaned_data = {'code': COUPON_CODE}

    def get_error_message_from_request(self):
        return list(get_messages(self.request))[-1].message

    def assert_response(self, **kwargs):
        self.assert_form_valid_message(kwargs['messages'][0]['user_message'])

    def assert_response_redirect(self, expected_redirect_url):
        resp = self.view.form_valid(self.form)
        self.assertIsInstance(resp, HttpResponseRedirect)
        self.assertEqual(resp.url, expected_redirect_url)

    def assert_form_valid_message(self, expected):
        """ Asserts the expected message is logged via messages framework when the
        view's form_valid method is called. """
        self.view.form_valid(self.form)

        actual = self.get_error_message_from_request()
        self.assertEqual(str(actual), expected)

    def test_voucher_valid_without_site(self):
        """ Verify coupon works when the sites on the coupon and request are the same. """
        self.mock_access_token_response()
        self.mock_account_api(self.request, self.user.username, data={'is_active': True})
        __, product = prepare_voucher(code=COUPON_CODE, site=self.request.site)
        self.basket.add_product(product)
        self.assert_form_valid_message("Coupon code '{code}' added to basket.".format(code=COUPON_CODE))

    def test_voucher_not_valid_for_other_site(self):
        """ Verify correct error message is returned when coupon is applied against on the wrong site. """
        other_site = SiteConfigurationFactory().site
        self.mock_access_token_response()
        self.mock_account_api(self.request, self.user.username, data={'is_active': True})
        voucher, product = prepare_voucher(code=COUPON_CODE, site=other_site)
        self.basket.add_product(product)
        self.assert_form_valid_message("Coupon code '{code}' is not valid for this basket.".format(code=voucher.code))

    def test_form_valid_without_basket_id(self):
        """ Verify the view redirects to the basket summary view if the basket has no ID.  """
        self.request.basket = Basket()
        response = self.view.form_valid(self.form)
        self.assertEqual(response.url, reverse('basket:summary'))

    def assert_basket_discounts(self, expected_offer_discounts=None, expected_voucher_discounts=None):
        """Helper to determine if the expected offer is applied to a basket.
        The basket is retrieved from the response because Oscar uses
        SimpleLazyObjects to operate with baskets."""
        expected_offer_discounts = expected_offer_discounts or []
        expected_voucher_discounts = expected_voucher_discounts or []

        response = self.client.get(reverse('basket:summary'))
        basket = response.context['basket']

        actual_offer_discounts = [discount['offer'] for discount in basket.offer_discounts]
        actual_voucher_discounts = [discount['offer'] for discount in basket.voucher_discounts]

        self.assertEqual(actual_offer_discounts, expected_offer_discounts)
        self.assertEqual(actual_voucher_discounts, expected_voucher_discounts)

    def test_coupon_applied_on_site_offer(self):
        """Coupon offer supersedes site offer."""
        self.mock_access_token_response()
        self.mock_account_api(self.request, self.user.username, data={'is_active': True})
        product_price = 100
        site_offer_discount = 20
        voucher_discount = 10

        voucher, product = prepare_voucher(benefit_value=voucher_discount)
        stockrecord = product.stockrecords.first()
        stockrecord.price_excl_tax = product_price
        stockrecord.save()

        _range = factories.RangeFactory(includes_all_products=True)
        site_offer = factories.ConditionalOfferFactory(
            offer_type=ConditionalOffer.SITE,
            benefit=factories.BenefitFactory(range=_range, value=site_offer_discount),
            condition=factories.ConditionFactory(type=Condition.COVERAGE, value=1, range=_range)
        )
        self.basket.add_product(product)
        # Only site offer is applied to the basket.
        self.assert_basket_discounts([site_offer])

        # Only the voucher offer is applied to the basket.
        self.client.post(reverse('basket:vouchers-add'), data={'code': voucher.code})
        self.assert_basket_discounts(expected_voucher_discounts=[voucher.offers.first()])

        # Site offer discount is still present after removing voucher.
        self.client.post(reverse('basket:vouchers-remove', kwargs={'pk': voucher.id}))
        self.assert_basket_discounts([site_offer])


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
