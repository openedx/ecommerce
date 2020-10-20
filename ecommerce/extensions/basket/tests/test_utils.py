

import datetime
import json
from uuid import uuid4

import ddt
import httpretty
import mock
import pytz
import requests
from django.db import transaction
from django.utils.timezone import now
from oscar.core.loading import get_model
from oscar.test.factories import BasketFactory, ProductFactory, RangeFactory
from waffle.testutils import override_flag

from ecommerce.core.constants import ENROLLMENT_CODE_PRODUCT_CLASS_NAME
from ecommerce.core.tests import toggle_switch
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.entitlements.utils import create_or_update_course_entitlement
from ecommerce.extensions.basket.tests.mixins import BasketMixin
from ecommerce.extensions.basket.utils import (
    ENTERPRISE_CATALOG_ATTRIBUTE_TYPE,
    add_utm_params_to_url,
    apply_voucher_on_basket_and_check_discount,
    attribute_cookie_data,
    get_basket_switch_data,
    get_payment_microfrontend_url_if_configured,
    is_duplicate_seat_attempt,
    prepare_basket
)
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.extensions.order.constants import DISABLE_REPEAT_ORDER_CHECK_SWITCH_NAME
from ecommerce.extensions.order.exceptions import AlreadyPlacedOrderException
from ecommerce.extensions.order.utils import UserAlreadyPlacedOrder
from ecommerce.extensions.partner.models import StockRecord
from ecommerce.extensions.payment.constants import DISABLE_MICROFRONTEND_FOR_BASKET_PAGE_FLAG_NAME
from ecommerce.extensions.test.factories import create_order, prepare_voucher
from ecommerce.referrals.models import Referral
from ecommerce.tests.testcases import TestCase, TransactionTestCase

Benefit = get_model('offer', 'Benefit')
Basket = get_model('basket', 'Basket')
BasketAttribute = get_model('basket', 'BasketAttribute')
BasketAttributeType = get_model('basket', 'BasketAttributeType')
BUNDLE = 'bundle_identifier'
Option = get_model('catalogue', 'Option')
Product = get_model('catalogue', 'Product')
ProductClass = get_model('catalogue', 'ProductClass')
TEST_BUNDLE_ID = '12345678-1234-1234-1234-123456789abc'


def timeoutException():
    raise requests.Timeout('Connection timed out')


@ddt.ddt
class BasketUtilsTests(DiscoveryTestMixin, BasketMixin, TestCase):
    """ Tests for basket utility functions. """

    def setUp(self):
        super(BasketUtilsTests, self).setUp()
        self.request.user = self.create_user()
        self.site_configuration.utm_cookie_name = 'test.edx.utm'
        toggle_switch(DISABLE_REPEAT_ORDER_CHECK_SWITCH_NAME, False)

    def mock_embargo_api(self, body=None, status=200):
        httpretty.register_uri(
            httpretty.GET,
            self.site_configuration.build_lms_url('/api/embargo/v1/course_access/'),
            status=status,
            body=body,
            content_type='application/json'
        )

    def test_add_utm_params_to_url(self):
        url = add_utm_params_to_url('/basket', [('utm_param', 'test'), ('other_param', 'test2')])
        self.assertEqual(url, '/basket?utm_param=test')

    def test_prepare_basket_with_voucher(self):
        """ Verify a basket is returned and contains a voucher and the voucher is applied. """
        # Prepare a product with price of 100 and a voucher with 10% discount for that product.
        product = ProductFactory(stockrecords__price_excl_tax=100)
        new_range = RangeFactory(products=[product])
        voucher, __ = prepare_voucher(_range=new_range, benefit_value=10)

        stock_record = StockRecord.objects.get(product=product)
        self.assertEqual(stock_record.price_excl_tax, 100.00)

        basket = prepare_basket(self.request, [product], voucher)
        self.assertIsNotNone(basket)
        self.assertEqual(basket.status, Basket.OPEN)
        self.assertEqual(basket.lines.count(), 1)
        self.assertEqual(basket.lines.first().product, product)
        self.assertEqual(basket.vouchers.count(), 1)
        self.assertIsNotNone(basket.applied_offers())
        self.assertEqual(basket.total_discount, 10.00)
        self.assertEqual(basket.total_excl_tax, 90.00)

    def test_prepare_basket_enrollment_with_voucher(self):
        """Verify the basket does not contain a voucher if enrollment code is added to it."""
        course = CourseFactory(partner=self.partner)
        course.create_or_update_seat('verified', False, 10, create_enrollment_code=True)
        enrollment_code = Product.objects.get(product_class__name=ENROLLMENT_CODE_PRODUCT_CLASS_NAME)
        voucher, product = prepare_voucher()

        basket = prepare_basket(self.request, [product], voucher)
        self.assertIsNotNone(basket)
        self.assertEqual(basket.all_lines()[0].product, product)
        self.assertTrue(basket.contains_a_voucher)

        basket = prepare_basket(self.request, [enrollment_code], voucher)
        self.assertIsNotNone(basket)
        self.assertEqual(basket.all_lines()[0].product, enrollment_code)
        self.assertFalse(basket.contains_a_voucher)

    def test_multiple_vouchers(self):
        """ Verify only the last entered voucher is contained in the basket. """
        product = ProductFactory(stockrecords__price_excl_tax=100)
        new_range = RangeFactory(products=[product, ])
        voucher1, __ = prepare_voucher(code='TEST1', _range=new_range, benefit_value=10)
        basket = prepare_basket(self.request, [product], voucher1)
        self.assertEqual(basket.vouchers.count(), 1)
        self.assertEqual(basket.vouchers.first(), voucher1)

        voucher2, __ = prepare_voucher(code='TEST2', _range=new_range, benefit_value=20)
        new_basket = prepare_basket(self.request, [product], voucher2)
        self.assertEqual(basket, new_basket)
        self.assertEqual(new_basket.vouchers.count(), 1)
        self.assertEqual(new_basket.vouchers.first(), voucher2)

    def test_prepare_basket_without_voucher(self):
        """ Verify a basket is returned and does not contain a voucher. """
        product = ProductFactory()
        basket = prepare_basket(self.request, [product])
        self.assertIsNotNone(basket)
        self.assertEqual(basket.status, Basket.OPEN)
        self.assertEqual(basket.lines.count(), 1)
        self.assertEqual(basket.lines.first().product, product)
        self.assertFalse(basket.vouchers.all())
        self.assertFalse(basket.applied_offers())

    def test_prepare_basket_with_multiple_products(self):
        """ Verify a basket is returned and only contains a single product. """
        product1 = ProductFactory(stockrecords__partner__short_code='test1')
        product2 = ProductFactory(stockrecords__partner__short_code='test2')
        prepare_basket(self.request, [product1])
        basket = prepare_basket(self.request, [product2])
        self.assertIsNotNone(basket)
        self.assertEqual(basket.status, Basket.OPEN)
        self.assertEqual(basket.lines.count(), 1)
        self.assertEqual(basket.lines.first().product, product2)
        self.assertEqual(basket.product_quantity(product2), 1)

    def test_prepare_basket_calls_attribution_method(self):
        """ Verify a basket is returned and referral method called. """
        with mock.patch('ecommerce.extensions.basket.utils.attribute_cookie_data') as mock_attr_method:
            product = ProductFactory()
            basket = prepare_basket(self.request, [product])
            mock_attr_method.assert_called_with(basket, self.request)

    @httpretty.activate
    def test_prepare_basket_embargo_check_fail(self):
        """ Verify an empty basket is returned after embargo check fails. """
        self.site_configuration.enable_embargo_check = True
        self.mock_access_token_response()
        self.mock_embargo_api(body=json.dumps({'access': False}))
        course = CourseFactory(partner=self.partner)
        product = course.create_or_update_seat('verified', False, 10)
        basket = prepare_basket(self.request, [product])
        self.assertEqual(basket.lines.count(), 0)

    @httpretty.activate
    def test_prepare_basket_embargo_with_enrollment_code(self):
        """ Verify a basket is returned after adding enrollment code. """
        self.site_configuration.enable_embargo_check = True
        self.mock_access_token_response()
        self.mock_embargo_api(body=json.dumps({'access': True}))
        course = CourseFactory(partner=self.partner)
        course.create_or_update_seat('verified', False, 10, create_enrollment_code=True)
        product = Product.objects.get(product_class__name=ENROLLMENT_CODE_PRODUCT_CLASS_NAME)
        basket = prepare_basket(self.request, [product])
        self.assertEqual(basket.lines.count(), 1)

    @httpretty.activate
    def test_prepare_basket_embargo_check_exception(self):
        """ Verify embargo check passes when API call throws an exception. """
        self.site_configuration.enable_embargo_check = True
        self.mock_access_token_response()
        self.mock_embargo_api(body=timeoutException)
        course = CourseFactory(partner=self.partner)
        product = course.create_or_update_seat('verified', False, 10)
        basket = prepare_basket(self.request, [product])
        self.assertEqual(basket.lines.count(), 1)

    def test_attribute_cookie_data_affiliate_cookie_lifecycle(self):
        """ Verify a basket is returned and referral captured if there is cookie info """

        # If there is no cookie info, verify no referral is created.
        basket = BasketFactory(owner=self.request.user, site=self.request.site)
        attribute_cookie_data(basket, self.request)
        with self.assertRaises(Referral.DoesNotExist):
            Referral.objects.get(basket=basket)

        # If there is cookie info, verify a referral is captured
        affiliate_id = 'test_affiliate'
        self.request.COOKIES['affiliate_id'] = affiliate_id
        attribute_cookie_data(basket, self.request)
        # test affiliate id from cookie saved in referral
        referral = Referral.objects.get(basket_id=basket.id)
        self.assertEqual(referral.affiliate_id, affiliate_id)

        # update cookie
        new_affiliate_id = 'new_affiliate'
        self.request.COOKIES['affiliate_id'] = new_affiliate_id
        attribute_cookie_data(basket, self.request)

        # test new affiliate id saved
        referral = Referral.objects.get(basket_id=basket.id)
        self.assertEqual(referral.affiliate_id, new_affiliate_id)

        # expire cookie
        del self.request.COOKIES['affiliate_id']
        attribute_cookie_data(basket, self.request)

        # test referral record is deleted when no cookie set
        with self.assertRaises(Referral.DoesNotExist):
            Referral.objects.get(basket_id=basket.id)

    def test_attribute_cookie_data_utm_cookie_lifecycle(self):
        """ Verify a basket is returned and referral captured. """
        utm_source = 'test-source'
        utm_medium = 'test-medium'
        utm_campaign = 'test-campaign'
        utm_term = 'test-term'
        utm_content = 'test-content'
        utm_created_at = 1475590280823
        expected_created_at = datetime.datetime.fromtimestamp(int(utm_created_at) / float(1000), tz=pytz.UTC)

        utm_cookie = {
            'utm_source': utm_source,
            'utm_medium': utm_medium,
            'utm_campaign': utm_campaign,
            'utm_term': utm_term,
            'utm_content': utm_content,
            'created_at': utm_created_at,
        }

        self.request.COOKIES[self.site_configuration.utm_cookie_name] = json.dumps(utm_cookie)
        basket = BasketFactory(owner=self.request.user, site=self.request.site)
        attribute_cookie_data(basket, self.request)

        # test utm data from cookie saved in referral
        referral = Referral.objects.get(basket_id=basket.id)
        self.assertEqual(referral.utm_source, utm_source)
        self.assertEqual(referral.utm_medium, utm_medium)
        self.assertEqual(referral.utm_campaign, utm_campaign)
        self.assertEqual(referral.utm_term, utm_term)
        self.assertEqual(referral.utm_content, utm_content)
        self.assertEqual(referral.utm_created_at, expected_created_at)

        # update cookie
        utm_source = 'test-source-new'
        utm_medium = 'test-medium-new'
        utm_campaign = 'test-campaign-new'
        utm_term = 'test-term-new'
        utm_content = 'test-content-new'
        utm_created_at = 1470590000000
        expected_created_at = datetime.datetime.fromtimestamp(int(utm_created_at) / float(1000), tz=pytz.UTC)

        new_utm_cookie = {
            'utm_source': utm_source,
            'utm_medium': utm_medium,
            'utm_campaign': utm_campaign,
            'utm_term': utm_term,
            'utm_content': utm_content,
            'created_at': utm_created_at,
        }
        self.request.COOKIES[self.site_configuration.utm_cookie_name] = json.dumps(new_utm_cookie)
        attribute_cookie_data(basket, self.request)

        # test new utm data saved
        referral = Referral.objects.get(basket_id=basket.id)
        self.assertEqual(referral.utm_source, utm_source)
        self.assertEqual(referral.utm_medium, utm_medium)
        self.assertEqual(referral.utm_campaign, utm_campaign)
        self.assertEqual(referral.utm_term, utm_term)
        self.assertEqual(referral.utm_content, utm_content)
        self.assertEqual(referral.utm_created_at, expected_created_at)

        # expire cookie
        del self.request.COOKIES[self.site_configuration.utm_cookie_name]
        attribute_cookie_data(basket, self.request)

        # test referral record is deleted when no cookie set
        with self.assertRaises(Referral.DoesNotExist):
            Referral.objects.get(basket_id=basket.id)

    def test_attribute_cookie_data_multiple_cookies(self):
        """ Verify a basket is returned and referral captured. """
        utm_source = 'test-source'
        utm_medium = 'test-medium'
        utm_campaign = 'test-campaign'
        utm_term = 'test-term'
        utm_content = 'test-content'
        utm_created_at = 1475590280823

        utm_cookie = {
            'utm_source': utm_source,
            'utm_medium': utm_medium,
            'utm_campaign': utm_campaign,
            'utm_term': utm_term,
            'utm_content': utm_content,
            'created_at': utm_created_at,
        }

        affiliate_id = 'affiliate'

        self.request.COOKIES[self.site_configuration.utm_cookie_name] = json.dumps(utm_cookie)
        self.request.COOKIES['affiliate_id'] = affiliate_id
        basket = BasketFactory(owner=self.request.user, site=self.request.site)
        attribute_cookie_data(basket, self.request)

        # test affiliate id & UTM data from cookie saved in referral
        referral = Referral.objects.get(basket_id=basket.id)
        expected_created_at = datetime.datetime.fromtimestamp(int(utm_created_at) / float(1000), tz=pytz.UTC)
        self.assertEqual(referral.utm_source, utm_source)
        self.assertEqual(referral.utm_medium, utm_medium)
        self.assertEqual(referral.utm_campaign, utm_campaign)
        self.assertEqual(referral.utm_term, utm_term)
        self.assertEqual(referral.utm_content, utm_content)
        self.assertEqual(referral.utm_created_at, expected_created_at)
        self.assertEqual(referral.affiliate_id, affiliate_id)

        # expire 1 cookie
        del self.request.COOKIES[self.site_configuration.utm_cookie_name]
        attribute_cookie_data(basket, self.request)

        # test affiliate id still saved in referral but utm data removed
        referral = Referral.objects.get(basket_id=basket.id)
        self.assertEqual(referral.utm_source, '')
        self.assertEqual(referral.utm_medium, '')
        self.assertEqual(referral.utm_campaign, '')
        self.assertEqual(referral.utm_term, '')
        self.assertEqual(referral.utm_content, '')
        self.assertIsNone(referral.utm_created_at)
        self.assertEqual(referral.affiliate_id, affiliate_id)

        # expire other cookie
        del self.request.COOKIES['affiliate_id']
        attribute_cookie_data(basket, self.request)

        # test referral record is deleted when no cookies are set
        with self.assertRaises(Referral.DoesNotExist):
            Referral.objects.get(basket_id=basket.id)

    def test_prepare_basket_raises_exception_for_purchased_product(self):
        """
        Test prepare_basket raises AlreadyPlacedOrderException if the product is already purchased by user
        """
        order = create_order(user=self.request.user)
        product = order.lines.first().product

        with self.assertRaises(AlreadyPlacedOrderException):
            prepare_basket(self.request, [product])

        # If the switch is enabled, no validation should be performed.
        toggle_switch(DISABLE_REPEAT_ORDER_CHECK_SWITCH_NAME, True)
        prepare_basket(self.request, [product])

    def test_prepare_basket_for_purchased_enrollment_code(self):
        """
        Test prepare_basket returns basket with product even if its already been purchased by user
        """
        course = CourseFactory(partner=self.partner)
        course.create_or_update_seat('verified', False, 10, create_enrollment_code=True)
        enrollment_code = Product.objects.get(product_class__name=ENROLLMENT_CODE_PRODUCT_CLASS_NAME)
        with mock.patch.object(UserAlreadyPlacedOrder, 'user_already_placed_order', return_value=True):
            basket = prepare_basket(self.request, [enrollment_code])
            self.assertIsNotNone(basket)

    def test_prepare_basket_with_bundle(self):
        """
        Test prepare_basket updates or creates a basket attribute for the associated bundle
        """
        product = ProductFactory()
        request = self.request
        basket = prepare_basket(request, [product])
        with self.assertRaises(BasketAttribute.DoesNotExist):
            BasketAttribute.objects.get(basket=basket, attribute_type__name=BUNDLE)
        request.GET = {'bundle': TEST_BUNDLE_ID}
        basket = prepare_basket(request, [product])
        bundle_id = BasketAttribute.objects.get(basket=basket, attribute_type__name=BUNDLE).value_text
        self.assertEqual(bundle_id, TEST_BUNDLE_ID)

    def test_prepare_basket_with_bundle_voucher(self):
        """
        Test prepare_basket clears vouchers for a bundle
        """
        product = ProductFactory(stockrecords__price_excl_tax=100)
        new_range = RangeFactory(products=[product, ])
        voucher, __ = prepare_voucher(_range=new_range, benefit_value=10)

        request = self.request
        basket = prepare_basket(request, [product], voucher)
        self.assertTrue(basket.vouchers.all())
        request.GET = {'bundle': TEST_BUNDLE_ID}
        basket = prepare_basket(request, [product])
        self.assertFalse(basket.vouchers.all())

    def test_prepare_basket_attribute_delete(self):
        """
        Test prepare_basket removes the bundle attribute for a basket when a user is purchasing a single course
        """
        product = ProductFactory(categories=[], stockrecords__partner__short_code='second')
        request = self.request
        request.GET = {'bundle': TEST_BUNDLE_ID}
        basket = prepare_basket(request, [product])

        # Verify that the bundle attribute exists for the basket when bundle is added to basket
        bundle_id = BasketAttribute.objects.get(basket=basket, attribute_type__name=BUNDLE).value_text
        self.assertEqual(bundle_id, TEST_BUNDLE_ID)

        # Verify that the attribute is deleted when a non-bundle product is added to the basket
        request.GET = {}
        prepare_basket(request, [product])
        with self.assertRaises(BasketAttribute.DoesNotExist):
            BasketAttribute.objects.get(basket=basket, attribute_type__name=BUNDLE)

        # Verify that no exception is raised when no basket attribute exists fitting the delete statement parameters
        prepare_basket(request, [product])

    def test_prepare_basket_with_enterprise_catalog(self):
        """
        Test `prepare_basket` with enterprise catalog.
        """
        product = ProductFactory()
        request = self.request
        expected_enterprise_catalog_uuid = str(uuid4())
        request.GET = {'catalog': expected_enterprise_catalog_uuid}
        basket = prepare_basket(request, [product])

        # Verify that the enterprise catalog attribute exists for the basket
        # when basket is prepared with the value of provide catalog UUID
        enterprise_catalog_uuid = BasketAttribute.objects.get(
            basket=basket,
            attribute_type__name=ENTERPRISE_CATALOG_ATTRIBUTE_TYPE
        ).value_text
        assert expected_enterprise_catalog_uuid == enterprise_catalog_uuid

        # Now verify that `prepare_basket` method removes the enterprise
        # catalog attribute if there is no `catalog` query parameter in url
        request.GET = {}
        basket = prepare_basket(request, [product])

        # Verify that enterprise catalog attribute does not exists for a basket
        # when basket is prepared with the value of provided catalog UUID
        with self.assertRaises(BasketAttribute.DoesNotExist):
            BasketAttribute.objects.get(
                basket=basket,
                attribute_type__name=ENTERPRISE_CATALOG_ATTRIBUTE_TYPE
            )

    def test_basket_switch_data(self):
        """Verify the correct basket switch data (single vs. multi quantity) is retrieved."""
        __, seat, enrollment_code = self.prepare_course_seat_and_enrollment_code()
        seat_sku = StockRecord.objects.get(product=seat).partner_sku
        ec_sku = StockRecord.objects.get(product=enrollment_code).partner_sku
        entitlement = create_or_update_course_entitlement(
            'verified', 100, self.partner, 'foo-bar', 'Foo Bar Entitlement')

        __, partner_sku = get_basket_switch_data(seat)
        self.assertEqual(partner_sku, ec_sku)
        __, partner_sku = get_basket_switch_data(enrollment_code)
        self.assertEqual(partner_sku, seat_sku)
        # Entitlement products should not return a sku for this function
        __, partner_sku = get_basket_switch_data(entitlement)
        self.assertIsNone(partner_sku)

    def test_basket_switch_data_for_non_course_run_products(self):
        """
        Verify that no basket switch data is retrieved for product classes that
        do not relate to course_run instances.
        """
        COURSE_RUN_PRODUCT_CLASSES = ['Seat', 'Enrollment Code']

        for product_class in ProductClass.objects.all():
            product = ProductFactory(
                product_class=product_class,
                title='{} product title'.format(product_class.name),
                categories=None,
                stockrecords__partner=self.partner
            )

            # Verify that the StockRecord hunt is only attempted for course run products
            with mock.patch('ecommerce.extensions.basket.utils._find_seat_enrollment_toggle_sku') as mock_track:
                _, _ = get_basket_switch_data(product)
                if product.product_class.name in COURSE_RUN_PRODUCT_CLASSES:
                    self.assertEqual(mock_track.call_count, 1)
                else:
                    mock_track.assert_not_called()

    def test_prepare_basket_ignores_invalid_voucher(self):
        """
        Tests that prepare_basket validates provided voucher and
        does not applies it if invalid.
        """
        voucher_start_time = now() - datetime.timedelta(days=5)
        voucher_end_time = now() - datetime.timedelta(days=3)
        product = ProductFactory(stockrecords__partner__short_code='test1', stockrecords__price_excl_tax=100)
        expired_voucher, __ = prepare_voucher(start_datetime=voucher_start_time, end_datetime=voucher_end_time)

        basket = prepare_basket(self.request, [product], expired_voucher)
        self.assertIsNotNone(basket)
        self.assertEqual(basket.status, Basket.OPEN)
        self.assertEqual(basket.lines.count(), 1)
        self.assertEqual(basket.lines.first().product, product)
        self.assertEqual(basket.vouchers.count(), 0)

    def test_prepare_basket_applies_valid_voucher_argument(self):
        """
            Tests that prepare_basket applies a valid voucher passed as an
            an argument, even when there is also a valid voucher already on
            the basket.
        """
        product = ProductFactory(stockrecords__partner__short_code='test1', stockrecords__price_excl_tax=100)
        new_range = RangeFactory(products=[product])
        new_voucher, __ = prepare_voucher(code='xyz', _range=new_range, benefit_value=10)
        existing_voucher, __ = prepare_voucher(code='test', _range=new_range, benefit_value=50)

        basket = BasketFactory(owner=self.request.user, site=self.request.site)
        basket.vouchers.add(existing_voucher)
        self.assertEqual(basket.vouchers.count(), 1)

        basket = prepare_basket(self.request, [product], new_voucher)
        self.assertIsNotNone(basket)
        self.assertEqual(basket.vouchers.count(), 1)
        self.assertEqual(basket.vouchers.first().code, 'XYZ')
        self.assertEqual(basket.total_discount, 10.00)

    def test_prepare_basket_removes_existing_basket_invalid_voucher(self):
        """
        Tests that prepare_basket removes an existing basket voucher that is invalid
        for multiple products when used to purchase any of those products.
        """
        voucher_start_time = now() - datetime.timedelta(days=5)
        voucher_end_time = now() - datetime.timedelta(days=3)
        product = ProductFactory(stockrecords__partner__short_code='xyz', stockrecords__price_excl_tax=100)
        expired_voucher, __ = prepare_voucher(start_datetime=voucher_start_time, end_datetime=voucher_end_time)

        basket = BasketFactory(owner=self.request.user, site=self.request.site)
        basket.vouchers.add(expired_voucher)

        self.assertEqual(basket.vouchers.count(), 1)
        basket = prepare_basket(self.request, [product])
        self.assertIsNotNone(basket)
        self.assertEqual(basket.lines.first().product, product)
        self.assertEqual(basket.vouchers.count(), 0)

    def test_prepare_basket_removes_existing_basket_invalid_range_voucher(self):
        """
        Tests that prepare_basket removes an existing basket voucher that is not
        valid for the product and used to purchase that product.
        """
        product = ProductFactory(stockrecords__partner__short_code='xyz', stockrecords__price_excl_tax=100)
        invalid_range_voucher, __ = prepare_voucher()
        basket = BasketFactory(owner=self.request.user, site=self.request.site)

        basket.vouchers.add(invalid_range_voucher)
        basket = prepare_basket(self.request, [product])

        self.assertIsNotNone(basket)
        self.assertEqual(basket.lines.first().product, product)
        self.assertEqual(basket.vouchers.count(), 0)

    def test_prepare_basket_applies_existing_basket_valid_voucher(self):
        """
        Tests that prepare_basket applies an existing basket voucher that is valid
        for multiple products when used to purchase any of those products.
        """
        product = ProductFactory(stockrecords__partner__short_code='test1', stockrecords__price_excl_tax=100)

        new_range = RangeFactory(products=[product])
        voucher, __ = prepare_voucher(_range=new_range, benefit_value=10)

        basket = BasketFactory(owner=self.request.user, site=self.request.site)
        basket.vouchers.add(voucher)
        self.assertEqual(basket.vouchers.count(), 1)

        basket = prepare_basket(self.request, [product])
        self.assertIsNotNone(basket)
        self.assertEqual(basket.vouchers.count(), 1)
        self.assertEqual(basket.lines.first().product, product)
        self.assertIsNotNone(basket.applied_offers())
        self.assertEqual(basket.total_discount, 10.00)

    def test_apply_voucher_on_basket_and_check_discount_with_valid_voucher(self):
        """
        Tests apply_voucher_on_basket_and_check_discount when called with valid voucher
        applies voucher and returns the correct values.
        """
        basket = BasketFactory(owner=self.request.user, site=self.request.site)
        voucher, product = prepare_voucher()
        basket.add_product(product, 1)
        applied, msg = apply_voucher_on_basket_and_check_discount(voucher, self.request, basket)
        self.assertEqual(applied, True)
        self.assertIsNotNone(basket.applied_offers())
        self.assertEqual(msg, "Coupon code '{code}' added to basket.".format(code=voucher.code))

    def test_apply_voucher_on_basket_and_check_discount_with_invalid_voucher(self):
        """
        Tests apply_voucher_on_basket_and_check_discount when called with invalid voucher
        does not apply voucher and returns the correct values.
        """
        basket = BasketFactory(owner=self.request.user, site=self.request.site)
        product = ProductFactory(stockrecords__partner__short_code='test1', stockrecords__price_excl_tax=100)
        voucher, __ = prepare_voucher()
        basket.add_product(product, 1)
        applied, msg = apply_voucher_on_basket_and_check_discount(voucher, self.request, basket)
        self.assertEqual(applied, False)
        self.assertEqual(basket.applied_offers(), {})
        self.assertEqual(msg, 'Basket does not qualify for coupon code {code}.'.format(code=voucher.code))

    def test_apply_voucher_on_basket_and_check_discount_with_invalid_product(self):
        """
        Tests apply_voucher_on_basket_and_check_discount when called with invalid product
        does not apply voucher and returns the correct values.
        """
        basket = BasketFactory(owner=self.request.user, site=self.request.site)
        product = ProductFactory(stockrecords__partner__short_code='test1', stockrecords__price_excl_tax=0)
        voucher, __ = prepare_voucher(_range=RangeFactory(products=[product]))
        basket.add_product(product, 1)
        applied, msg = apply_voucher_on_basket_and_check_discount(voucher, self.request, basket)
        self.assertEqual(applied, False)
        self.assertEqual(basket.applied_offers(), {})
        self.assertEqual(msg, 'Basket does not qualify for coupon code {code}.'.format(code=voucher.code))

    def test_apply_voucher_on_basket_and_check_discount_with_multiple_vouchers(self):
        """
        Tests apply_voucher_on_basket_and_check_discount when called with a basket already
        containing a valid voucher it only checks the new voucher.
        """
        basket = BasketFactory(owner=self.request.user, site=self.request.site)
        product = ProductFactory(stockrecords__partner__short_code='test1', stockrecords__price_excl_tax=10)
        invalid_voucher, __ = prepare_voucher(code='TEST1')
        valid_voucher, __ = prepare_voucher(code='TEST2', _range=RangeFactory(products=[product]))
        basket.add_product(product, 1)
        basket.vouchers.add(valid_voucher)
        applied, msg = apply_voucher_on_basket_and_check_discount(invalid_voucher, self.request, basket)
        self.assertEqual(applied, False)
        self.assertEqual(msg, 'Basket does not qualify for coupon code {code}.'.format(code=invalid_voucher.code))

    @ddt.data(
        (True, '/payment', False, '/payment'),  # Microfrontend not disabled
        (True, '/payment', True, None),  # Microfrontend disabled
    )
    @ddt.unpack
    def test_disable_microfrontend_for_basket_page_flag(
            self,
            microfrontend_enabled,
            payment_microfrontend_url,
            disable_microfrontend_flag_active,
            expected_result
    ):
        """
        Verify that the `disable_microfrontend_for_basket_page_flag` correctly disables the microfrontend url retrieval
        """
        with override_flag(DISABLE_MICROFRONTEND_FOR_BASKET_PAGE_FLAG_NAME, active=disable_microfrontend_flag_active):
            self.site_configuration.enable_microfrontend_for_basket_page = microfrontend_enabled
            self.site_configuration.payment_microfrontend_url = payment_microfrontend_url
            self.assertEqual(get_payment_microfrontend_url_if_configured(self.request), expected_result)

    def test_prepare_basket_with_duplicate_seat(self):
        """ Verify a basket fixes the case where flush doesn't work and we attempt adding duplicate seat. """
        with mock.patch('ecommerce.extensions.basket.utils.Basket.flush'):
            product_type_seat, _ = ProductClass.objects.get_or_create(name='Seat')
            product1 = ProductFactory(stockrecords__partner__short_code='test1', product_class=product_type_seat)
            prepare_basket(self.request, [product1])
            basket = prepare_basket(self.request, [product1])  # try to add a duplicate seat
            self.assertEqual(basket.product_quantity(product1), 1)

    def test_is_duplicate_seat_attempt__seats(self):
        """ Verify we get a correct response for duplicate seat check (seats) """
        product_type_seat, _ = ProductClass.objects.get_or_create(name='Seat')
        product1 = ProductFactory(stockrecords__partner__short_code='test1', product_class=product_type_seat)
        product2 = ProductFactory(stockrecords__partner__short_code='test2', product_class=product_type_seat)
        seat_basket = prepare_basket(self.request, [product1])
        result_product1 = is_duplicate_seat_attempt(seat_basket, product1)
        result_product2 = is_duplicate_seat_attempt(seat_basket, product2)

        self.assertTrue(result_product1)
        self.assertFalse(result_product2)

    def test_is_duplicate_seat_attempt__enrollment_code(self):
        """ Verify we get a correct response for duplicate seat check (false for Enrollment code)"""
        enrollment_class, _ = ProductClass.objects.get_or_create(name='Enrollment Code')
        enrollment_product = ProductFactory(stockrecords__partner__short_code='test3', product_class=enrollment_class)
        basket_with_enrollment_code = prepare_basket(self.request, [enrollment_product])
        result_product3 = is_duplicate_seat_attempt(basket_with_enrollment_code, enrollment_product)

        self.assertFalse(result_product3)


class BasketUtilsTransactionTests(TransactionTestCase):
    def setUp(self):
        super(BasketUtilsTransactionTests, self).setUp()
        self.request.user = self.create_user()
        self.site_configuration.utm_cookie_name = 'test.edx.utm'
        toggle_switch(DISABLE_REPEAT_ORDER_CHECK_SWITCH_NAME, False)
        BasketAttributeType.objects.get_or_create(name=BUNDLE)
        Option.objects.get_or_create(name='Course Entitlement', code='course_entitlement', type=Option.OPTIONAL)

    def _setup_request_cookie(self):
        utm_campaign = 'test-campaign'
        utm_content = 'test-content'
        utm_created_at = 1475590280823

        utm_cookie = {
            'utm_campaign': utm_campaign,
            'utm_content': utm_content,
            'created_at': utm_created_at,
        }

        affiliate_id = 'affiliate'

        self.request.COOKIES[self.site_configuration.utm_cookie_name] = json.dumps(utm_cookie)
        self.request.COOKIES['affiliate_id'] = affiliate_id

    def test_attribution_atomic_transaction(self):
        """
        Verify that an IntegrityError raised while creating a referral
        does not prevent a basket from being created.
        """
        self._setup_request_cookie()
        product = ProductFactory()
        existing_basket = Basket.get_basket(self.request.user, self.request.site)
        existing_referral = Referral(basket=existing_basket, site=self.request.site)
        # Let's save an existing referral object to force the duplication happen in database
        existing_referral.save()

        with transaction.atomic():
            with mock.patch('ecommerce.extensions.basket.utils._referral_from_basket_site') as mock_get_referral:
                # Mock to return a duplicated referral object, so when saved, a DB integrity error is raised
                # Mocking with side_effect to raise IntegrityError will not roll back the DB transaction
                # We actually would handle the exception in the attribute_cookie_data method.
                # Only causing the true database conflict like what we are doing here, would cause the roll back
                mock_get_referral.return_value = Referral(basket=existing_basket, site=self.request.site)
                basket = prepare_basket(self.request, [product])
                referral = Referral.objects.filter(basket=basket)

        self.assertEqual(len(referral), 1)
        self.assertIsNotNone(basket)
        self.assertTrue(basket.id > 0)
        self.assertEqual(basket.status, Basket.OPEN)
        self.assertEqual(basket.lines.count(), 1)
        self.assertEqual(basket.lines.first().product, product)
