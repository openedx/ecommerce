import datetime
import json
import mock

import ddt
from django.db import transaction
from django.test import RequestFactory, TransactionTestCase
from oscar.core.loading import get_model
from oscar.test.factories import BasketFactory, ProductFactory, RangeFactory, VoucherFactory
import pytz

from ecommerce.core.constants import ENROLLMENT_CODE_PRODUCT_CLASS_NAME, ENROLLMENT_CODE_SWITCH
from ecommerce.core.tests import toggle_switch
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.basket.utils import prepare_basket, attribute_cookie_data
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.tests.mixins import UserMixin
from ecommerce.extensions.partner.models import StockRecord
from ecommerce.extensions.test.factories import prepare_voucher
from ecommerce.referrals.models import Referral
from ecommerce.tests.factories import SiteConfigurationFactory
from ecommerce.tests.testcases import TestCase

Benefit = get_model('offer', 'Benefit')
Basket = get_model('basket', 'Basket')
Product = get_model('catalogue', 'Product')


@ddt.ddt
class BasketUtilsTests(CourseCatalogTestMixin, TestCase):
    """ Tests for basket utility functions. """

    def setUp(self):
        super(BasketUtilsTests, self).setUp()
        self.request = RequestFactory()
        self.request.COOKIES = {}
        self.request.user = self.create_user()
        site_configuration = SiteConfigurationFactory(partner__name='Tester')
        site_configuration.utm_cookie_name = 'test.edx.utm'
        self.request.site = site_configuration.site

    def test_prepare_basket_with_voucher(self):
        """ Verify a basket is returned and contains a voucher and the voucher is applied. """
        # Prepare a product with price of 100 and a voucher with 10% discount for that product.
        product = ProductFactory(stockrecords__price_excl_tax=100)
        new_range = RangeFactory(products=[product, ])
        voucher, product = prepare_voucher(_range=new_range, benefit_value=10)

        stock_record = StockRecord.objects.get(product=product)
        self.assertEqual(stock_record.price_excl_tax, 100.00)

        basket = prepare_basket(self.request, product, voucher)
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
        course = CourseFactory()
        toggle_switch(ENROLLMENT_CODE_SWITCH, True)
        course.create_or_update_seat('verified', False, 10, self.partner, create_enrollment_code=True)
        enrollment_code = Product.objects.get(product_class__name=ENROLLMENT_CODE_PRODUCT_CLASS_NAME)
        voucher, product = prepare_voucher()

        basket = prepare_basket(self.request, product, voucher)
        self.assertIsNotNone(basket)
        self.assertEqual(basket.all_lines()[0].product, product)
        self.assertTrue(basket.contains_a_voucher)

        basket = prepare_basket(self.request, enrollment_code, voucher)
        self.assertIsNotNone(basket)
        self.assertEqual(basket.all_lines()[0].product, enrollment_code)
        self.assertFalse(basket.contains_a_voucher)

    def test_multiple_vouchers(self):
        """ Verify only the last entered voucher is contained in the basket. """
        product = ProductFactory()
        voucher1 = VoucherFactory(code='FIRST')
        basket = prepare_basket(self.request, product, voucher1)
        self.assertEqual(basket.vouchers.count(), 1)
        self.assertEqual(basket.vouchers.first(), voucher1)

        voucher2 = VoucherFactory(code='SECOND')
        new_basket = prepare_basket(self.request, product, voucher2)
        self.assertEqual(basket, new_basket)
        self.assertEqual(new_basket.vouchers.count(), 1)
        self.assertEqual(new_basket.vouchers.first(), voucher2)

    def test_prepare_basket_without_voucher(self):
        """ Verify a basket is returned and does not contain a voucher. """
        product = ProductFactory()
        basket = prepare_basket(self.request, product)
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
        basket = prepare_basket(self.request, product1)
        basket = prepare_basket(self.request, product2)
        self.assertIsNotNone(basket)
        self.assertEqual(basket.status, Basket.OPEN)
        self.assertEqual(basket.lines.count(), 1)
        self.assertEqual(basket.lines.first().product, product2)
        self.assertEqual(basket.product_quantity(product2), 1)

    def test_prepare_basket_calls_attribution_method(self):
        """ Verify a basket is returned and referral method called. """
        with mock.patch('ecommerce.extensions.basket.utils.attribute_cookie_data') as mock_attr_method:
            product = ProductFactory()
            basket = prepare_basket(self.request, product)
            mock_attr_method.assert_called_with(basket, self.request)

    def test_attribute_cookie_data_affiliate_cookie_lifecycle(self):
        """ Verify a basket is returned and referral captured. """
        affiliate_id = 'test_affiliate'
        self.request.COOKIES['affiliate_id'] = affiliate_id
        basket = BasketFactory(owner=self.request.user, site=self.request.site)
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

        self.request.COOKIES['test.edx.utm'] = json.dumps(utm_cookie)
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
        self.request.COOKIES['test.edx.utm'] = json.dumps(new_utm_cookie)
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
        del self.request.COOKIES['test.edx.utm']
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

        self.request.COOKIES['test.edx.utm'] = json.dumps(utm_cookie)
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
        del self.request.COOKIES['test.edx.utm']
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


class BasketUtilsTranactionTests(UserMixin, TransactionTestCase):
    def setUp(self):
        super(BasketUtilsTranactionTests, self).setUp()
        self.request = RequestFactory()
        self.request.COOKIES = {}
        self.request.user = self.create_user()
        site_configuration = SiteConfigurationFactory(partner__name='Tester')
        site_configuration.utm_cookie_name = 'test.edx.utm'
        self.request.site = site_configuration.site

    def test_attribution_atomic_transation(self):
        with transaction.atomic():
            basket = BasketFactory(owner=self.request.user, site=self.request.site)
            StockRecord.objects.create(partner_sku="TEST123", product_id=1, partner_id=1)
            with mock.patch('ecommerce.extensions.basket.utils._referral_from_basket_site') as mock_get_referral:
                mock_get_referral.side_effect = AttributeError()
                attribute_cookie_data(basket, self.request)

        self.assertIsNotNone(Basket.objects.get(id=basket.id))
        self.assertIsNotNone(StockRecord.objects.get(partner_sku="TEST123"))
