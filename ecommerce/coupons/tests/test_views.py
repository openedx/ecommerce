import datetime

import ddt
import httpretty
import pytz
from django.conf import settings
from django.core.urlresolvers import reverse
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _
from oscar.core.loading import get_class, get_model
from oscar.test.factories import (
    ConditionalOfferFactory, OrderFactory, OrderLineFactory, RangeFactory, VoucherFactory
)
from oscar.test.utils import RequestFactory

from ecommerce.core.url_utils import get_lms_url
from ecommerce.coupons.tests.mixins import CouponMixin
from ecommerce.coupons.views import get_voucher_and_products_from_code, voucher_is_valid
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.api import exceptions
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.extensions.test.factories import prepare_voucher
from ecommerce.tests.mixins import LmsApiMockMixin
from ecommerce.tests.testcases import TestCase

Applicator = get_class('offer.utils', 'Applicator')
Basket = get_model('basket', 'Basket')
Benefit = get_model('offer', 'Benefit')
Catalog = get_model('catalogue', 'Catalog')
Course = get_model('courses', 'Course')
Product = get_model('catalogue', 'Product')
OrderLineVouchers = get_model('voucher', 'OrderLineVouchers')
StockRecord = get_model('partner', 'StockRecord')
Voucher = get_model('voucher', 'Voucher')
VoucherApplication = get_model('voucher', 'VoucherApplication')

CONTENT_TYPE = 'application/json'
COUPON_CODE = 'COUPONTEST'


class CouponAppViewTests(TestCase):
    path = reverse('coupons:app', args=[''])

    def setUp(self):
        super(CouponAppViewTests, self).setUp()

    def test_login_required(self):
        """ Users are required to login before accessing the view. """
        self.client.logout()
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 302)
        self.assertIn(settings.LOGIN_URL, response.url)

    def test_staff_user_required(self):
        """ Verify the view is only accessible to staff users. """
        user = self.create_user(is_staff=False)
        self.client.login(username=user.username, password=self.password)
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 404)

        user = self.create_user(is_staff=True)
        self.client.login(username=user.username, password=self.password)
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)


class GetVoucherTests(TestCase):
    def test_get_voucher_and_products_from_code(self):
        """ Verify that get_voucher_and_products_from_code() returns products and voucher. """
        original_voucher, original_product = prepare_voucher(code=COUPON_CODE)
        voucher, products = get_voucher_and_products_from_code(code=COUPON_CODE)

        self.assertIsNotNone(voucher)
        self.assertEqual(voucher, original_voucher)
        self.assertEqual(voucher.code, COUPON_CODE)
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0], original_product)

    def test_no_product(self):
        """ Verify that an exception is raised if there is no product. """
        voucher = VoucherFactory(code='NOPRODUCT')
        offer = ConditionalOfferFactory()
        voucher.offers.add(offer)

        with self.assertRaises(exceptions.ProductNotFoundError):
            get_voucher_and_products_from_code(code='NOPRODUCT')

    def test_get_non_existing_voucher(self):
        """ Verify that get_voucher_and_products_from_code() raises exception for a non-existing voucher. """
        with self.assertRaises(Voucher.DoesNotExist):
            get_voucher_and_products_from_code(code='INVALID')

    def test_valid_voucher(self):
        """ Verify voucher_is_valid() assess that the voucher is valid. """
        voucher, product = prepare_voucher(code=COUPON_CODE)
        request = RequestFactory().request()
        valid, msg = voucher_is_valid(voucher=voucher, products=[product], request=request)
        self.assertTrue(valid)
        self.assertEquals(msg, '')

    def test_no_voucher(self):
        """ Verify voucher_is_valid() assess that the voucher is invalid. """
        valid, msg = voucher_is_valid(voucher=None, products=None, request=None)
        self.assertFalse(valid)
        self.assertEqual(msg, _('Coupon does not exist'))

    def test_expired_voucher(self):
        """ Verify voucher_is_valid() assess that the voucher has expired. """
        start_datetime = now() - datetime.timedelta(days=20)
        end_datetime = now() - datetime.timedelta(days=10)
        voucher, product = prepare_voucher(code=COUPON_CODE, start_datetime=start_datetime, end_datetime=end_datetime)
        valid, msg = voucher_is_valid(voucher=voucher, products=[product], request=None)
        self.assertFalse(valid)
        self.assertEqual(msg, _('This coupon code has expired.'))

    def test_future_voucher(self):
        """ Verify voucher_is_valid() assess that the voucher has not started yet. """
        start_datetime = now() + datetime.timedelta(days=10)
        end_datetime = now() + datetime.timedelta(days=20)
        voucher, product = prepare_voucher(code=COUPON_CODE, start_datetime=start_datetime, end_datetime=end_datetime)
        valid, msg = voucher_is_valid(voucher=voucher, products=[product], request=None)
        self.assertFalse(valid)
        self.assertEqual(msg, _('This coupon code is not yet valid.'))

    def test_voucher_unavailable_to_buy(self):
        """ Verify that False is returned for unavialable products. """
        request = RequestFactory().request()
        voucher, product = prepare_voucher(code=COUPON_CODE)
        product.expires = pytz.utc.localize(datetime.datetime.min)
        valid, __ = voucher_is_valid(voucher=voucher, products=[product], request=request)
        self.assertFalse(valid)

    def assert_error_messages(self, voucher, product, user, error_msg):
        """ Assert the proper error message is returned. """
        voucher.offers.first().record_usage(discount={'freq': 1, 'discount': 1})
        request = RequestFactory().request()
        request.user = user
        valid, msg = voucher_is_valid(voucher=voucher, products=[product], request=request)
        self.assertFalse(valid)
        self.assertEqual(msg, error_msg)

    def test_used_voucher(self):
        """ Verify voucher_is_valid() assess that the voucher is unavailable. """
        voucher, product = prepare_voucher(code=COUPON_CODE)
        user = self.create_user()
        order = OrderFactory()
        VoucherApplication.objects.create(voucher=voucher, user=user, order=order)
        error_msg = _('This coupon has already been used')
        self.assert_error_messages(voucher, product, user, error_msg)

    def test_usage_exceeded_coupon(self):
        """ Verify voucher_is_valid() assess that the voucher exceeded it's usage limit. """
        voucher, product = prepare_voucher(code=COUPON_CODE, usage=Voucher.ONCE_PER_CUSTOMER, max_usage=1)
        user = self.create_user()
        error_msg = _('This coupon code is no longer available.')
        self.assert_error_messages(voucher, product, user, error_msg)

    def test_once_per_customer_voucher(self):
        """ Verify the coupon is valid for anonymous users. """
        voucher, product = prepare_voucher(usage=Voucher.ONCE_PER_CUSTOMER)
        request = RequestFactory().request()
        valid, msg = voucher_is_valid(voucher=voucher, products=[product], request=request)
        self.assertTrue(valid)
        self.assertEqual(msg, '')


@httpretty.activate
@ddt.ddt
class CouponOfferViewTests(CourseCatalogTestMixin, LmsApiMockMixin, TestCase):
    path = reverse('coupons:offer')
    path_with_code = '{path}?code={code}'.format(path=path, code=COUPON_CODE)

    def setUp(self):
        super(CouponOfferViewTests, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)

    def prepare_course_information(self):
        """ Helper function to prepare an API endpoint that provides course information. """
        course, __, stock_record = self.prepare_stock_record()
        catalog = Catalog.objects.create(name='Test catalog', partner=self.partner)
        catalog.stock_records.add(stock_record)
        _range = RangeFactory(catalog=catalog)
        self.mock_course_api_response(course=course)
        return _range

    def prepare_stock_record(self, course_name='Test course'):
        course = CourseFactory(name=course_name)
        seat = course.create_or_update_seat('verified', True, 50, self.partner)
        stock_record = StockRecord.objects.get(product=seat)
        return course, seat, stock_record

    def test_no_code(self):
        """ Verify a proper response is returned when no code is supplied. """
        response = self.client.get(self.path)
        self.assertEqual(response.context['error'], _('This coupon code is invalid.'))

    def test_invalid_voucher(self):
        """ Verify an error is returned when voucher with provided code does not exist. """
        url = self.path + '?code={}'.format('DOESNTEXIST')
        response = self.client.get(url)
        self.assertEqual(response.context['error'], _('Coupon does not exist'))

    def test_expired_voucher(self):
        """ Verify proper response is returned for expired vouchers. """
        start_datetime = now() - datetime.timedelta(days=20)
        end_datetime = now() - datetime.timedelta(days=10)
        prepare_voucher(code='EXPIRED', start_datetime=start_datetime, end_datetime=end_datetime)

        url = self.path + '?code={}'.format('EXPIRED')
        response = self.client.get(url)
        self.assertEqual(response.context['error'], _('This coupon code has expired.'))

    def test_no_product(self):
        """ Verify an error is returned for voucher with no product. """
        no_product_range = RangeFactory()
        prepare_voucher(code='NOPRODUCT', _range=no_product_range)
        url = self.path + '?code={}'.format('NOPRODUCT')
        response = self.client.get(url)
        self.assertEqual(response.context['error'], _('The voucher is not applicable to your current basket.'))


class CouponRedeemViewTests(CouponMixin, CourseCatalogTestMixin, LmsApiMockMixin, TestCase):
    redeem_url = reverse('coupons:redeem')

    def setUp(self):
        super(CouponRedeemViewTests, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)
        self.course, self.seat = self.create_course_and_seat(
            seat_type='verified',
            id_verification=True,
            price=50,
            partner=self.partner
        )
        self.stock_record = StockRecord.objects.get(product=self.seat)
        self.catalog = Catalog.objects.create(partner=self.partner)
        self.catalog.stock_records.add(StockRecord.objects.get(product=self.seat))
        self.student_dashboard_url = get_lms_url(self.site.siteconfiguration.student_dashboard_url)

    def create_and_test_coupon(self):
        """ Creates enrollment code coupon. """
        self.create_coupon(catalog=self.catalog, code=COUPON_CODE)
        self.assertEqual(Voucher.objects.filter(code=COUPON_CODE).count(), 1)

    def assert_redemption_page_redirects(self, expected_url, target=200):
        """ Verify redirect from redeem page to expected page. """
        url = self.redeem_url + '?code={}&sku={}'.format(COUPON_CODE, self.stock_record.partner_sku)
        response = self.client.get(url)
        self.assertRedirects(response, expected_url, status_code=302, target_status_code=target)

    def test_login_required(self):
        """ Users are required to login before accessing the view. """
        self.client.logout()
        response = self.client.get(self.redeem_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(settings.LOGIN_URL, response.url)

    def test_code_not_provided(self):
        """ Verify a response message is returned when no code is provided. """
        url_without_code = '{}?sku={}'.format(self.redeem_url, self.stock_record.partner_sku)
        response = self.client.get(url_without_code)
        self.assertEqual(response.context['error'], _('Code not provided.'))

    def test_sku_not_provided(self):
        """ Verify a response message is returned when no SKU is provided. """
        url_without_sku = '{}?code={}'.format(self.redeem_url, COUPON_CODE)
        response = self.client.get(url_without_sku)
        self.assertEqual(response.context['error'], _('SKU not provided.'))

    def test_invalid_voucher(self):
        """ Verify an error is returned when voucher does not exist. """
        code = 'DOESNTEXIST'
        url = self.redeem_url + '?code={}&sku={}'.format(code, self.stock_record.partner_sku)
        response = self.client.get(url)
        msg = 'No voucher found with code {code}'.format(code=code)
        self.assertEqual(response.context['error'], _(msg))

    def test_no_product(self):
        """ Verify an error is returned when a stock record for the provided SKU doesn't exist. """
        self.create_and_test_coupon()
        url = self.redeem_url + '?code={}&sku=INVALID'.format(COUPON_CODE)
        response = self.client.get(url)
        self.assertEqual(response.context['error'], _('The product does not exist.'))

    @httpretty.activate
    def test_basket_redirect_discount_code(self):
        """ Verify the view redirects to the basket single-item view when a discount code is provided. """
        self.mock_course_api_response(course=self.course)
        self.create_coupon(catalog=self.catalog, code=COUPON_CODE, benefit_value=5)
        expected_url = self.get_full_url(path=reverse('basket:summary'))
        self.assert_redemption_page_redirects(expected_url)

    @httpretty.activate
    def test_basket_redirect_enrollment_code(self):
        """ Verify the view redirects to LMS when an enrollment code is provided. """
        self.create_and_test_coupon()
        httpretty.register_uri(httpretty.GET, self.student_dashboard_url, status=301)
        self.assert_redemption_page_redirects(self.student_dashboard_url, target=301)

    @httpretty.activate
    def test_multiple_vouchers(self):
        """ Verify a redirect to LMS happens when a basket with already existing vouchers is used. """
        self.create_and_test_coupon()
        basket = Basket.get_basket(self.user, self.site)
        basket.vouchers.add(Voucher.objects.get(code=COUPON_CODE))
        httpretty.register_uri(httpretty.GET, self.student_dashboard_url, status=301)
        self.assert_redemption_page_redirects(self.student_dashboard_url, target=301)


class EnrollmentCodeCsvViewTests(TestCase):
    """ Tests for the EnrollmentCodeCsvView view. """
    path = 'coupons:enrollment_code_csv'

    def setUp(self):
        super(EnrollmentCodeCsvViewTests, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)

    def test_invalid_order_number(self):
        """ Verify a 404 error is raised for an invalid order number. """
        response = self.client.get(reverse(self.path, args=['INVALID']))
        self.assertEqual(response.status_code, 404)

    def test_invalid_user(self):
        """ Verify an unauthorized request is redirected to the LMS dashboard. """
        order = OrderFactory()
        order.user = self.create_user()
        response = self.client.get(reverse(self.path, args=[order.number]))
        self.assertEqual(response.status_code, 302)
        redirect_location = get_lms_url('dashboard')
        self.assertEqual(response['location'], redirect_location)

    def test_successful_response(self):
        """ Verify a successful response is returned. """
        voucher = VoucherFactory(code='ENROLLMENT')
        order = OrderFactory(user=self.user)
        line = OrderLineFactory(order=order)
        order_line_vouchers = OrderLineVouchers.objects.create(line=line)
        order_line_vouchers.vouchers.add(voucher)
        response = self.client.get(reverse(self.path, args=[order.number]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['content-type'], 'text/csv')
