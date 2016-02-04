import datetime

import ddt
from django.conf import settings
from django.core.urlresolvers import reverse
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _
import httpretty
from oscar.core.loading import get_class, get_model
from oscar.test.factories import OrderFactory, ConditionalOfferFactory, VoucherFactory, RangeFactory
from oscar.test.utils import RequestFactory
import pytz

from ecommerce.coupons.views import get_voucher_from_code, voucher_is_valid
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.test.factories import create_coupon, prepare_voucher
from ecommerce.settings import get_lms_url
from ecommerce.tests.mixins import LmsApiMockMixin
from ecommerce.tests.testcases import TestCase

Applicator = get_class('offer.utils', 'Applicator')
Basket = get_model('basket', 'Basket')
Benefit = get_model('offer', 'Benefit')
Catalog = get_model('catalogue', 'Catalog')
Course = get_model('courses', 'Course')
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

    def test_get_voucher_from_code(self):
        """ Verify that get_voucher_from_code() returns product and voucher. """
        original_voucher, original_product = prepare_voucher(code=COUPON_CODE)
        voucher, product = get_voucher_from_code(code=COUPON_CODE)

        self.assertIsNotNone(voucher)
        self.assertEqual(voucher, original_voucher)
        self.assertEqual(voucher.code, COUPON_CODE)
        self.assertIsNotNone(product)
        self.assertEqual(product, original_product)

    def test_no_product(self):
        """ Verify that None is returned if there is no product. """
        voucher = VoucherFactory(code='NOPRODUCT')
        offer = ConditionalOfferFactory()
        voucher.offers.add(offer)
        voucher, product = get_voucher_from_code(code='NOPRODUCT')

        self.assertIsNotNone(voucher)
        self.assertEqual(voucher.code, 'NOPRODUCT')
        self.assertIsNone(product)

    def test_get_non_existing_voucher(self):
        """ Verify that get_voucher_from_code() returns None for a non-existing voucher. """
        voucher, product = get_voucher_from_code(code='INVALID')
        self.assertIsNone(voucher)
        self.assertIsNone(product)

    def test_valid_voucher(self):
        """ Verify voucher_is_valid() assess that the voucher is valid. """
        voucher, product = prepare_voucher(code=COUPON_CODE)
        request = RequestFactory().request()
        valid, msg = voucher_is_valid(voucher=voucher, product=product, request=request)
        self.assertTrue(valid)
        self.assertEquals(msg, '')

    def test_no_voucher(self):
        """ Verify voucher_is_valid() assess that the voucher is invalid. """
        valid, msg = voucher_is_valid(voucher=None, product=None, request=None)
        self.assertFalse(valid)
        self.assertEqual(msg, _('Coupon does not exist'))

    def test_expired_voucher(self):
        """ Verify voucher_is_valid() assess that the voucher has expired. """
        future_datetime = now() + datetime.timedelta(days=10)
        voucher, product = prepare_voucher(code=COUPON_CODE, start_datetime=future_datetime)
        valid, msg = voucher_is_valid(voucher=voucher, product=product, request=None)
        self.assertFalse(valid)
        self.assertEqual(msg, _('Coupon expired'))

    def test_voucher_unavailable_to_buy(self):
        """ Verify that False is returned for unavialable products. """
        request = RequestFactory().request()
        voucher, product = prepare_voucher(code=COUPON_CODE)
        product.expires = pytz.utc.localize(datetime.datetime.min)
        valid, __ = voucher_is_valid(voucher=voucher, product=product, request=request)
        self.assertFalse(valid)

    def test_used_voucher(self):
        """ Verify voucher_is_valid() assess that the voucher is unavailable. """
        voucher, product = prepare_voucher(code=COUPON_CODE)
        order = OrderFactory()
        user = self.create_user()
        VoucherApplication.objects.create(voucher=voucher, user=user, order=order)
        request = RequestFactory().request()
        valid, msg = voucher_is_valid(voucher=voucher, product=product, request=request)
        self.assertFalse(valid)
        self.assertEqual(msg, _('This coupon has already been used'))


@httpretty.activate
@ddt.ddt
class CouponOfferViewTests(LmsApiMockMixin, TestCase):
    path = reverse('coupons:offer')
    path_with_code = '{path}?code={code}'.format(path=path, code=COUPON_CODE)

    def setUp(self):
        super(CouponOfferViewTests, self).setUp()
        self.mock_footer_api_response()

    def prepare_course_information(self):
        """ Helper function to prepare an API endpoint that provides course information. """
        course = CourseFactory(name='Test course')
        seat = course.create_or_update_seat('verified', True, 50, self.partner)
        stock_record = StockRecord.objects.get(product=seat)
        catalog = Catalog.objects.create(name='Test catalog', partner=self.partner)
        catalog.stock_records.add(stock_record)
        _range = RangeFactory(catalog=catalog)
        self.mock_course_api_response(course=course)
        return _range

    def test_no_code(self):
        """ Verify a proper response is returned when no code is supplied. """
        response = self.client.get(self.path)
        self.assertEqual(response.context['error'], _('This coupon code is invalid.'))

    def test_invalid_voucher(self):
        """ Verify a proper response is returned when voucher with provided code does not exist. """
        url = self.path + '?code={}'.format('DOESNTEXIST')
        response = self.client.get(url)
        self.assertEqual(response.context['error'], _('Coupon does not exist'))

    def test_course_information_error(self):
        """ Verify a response is returned when course information is not accessable. """
        course = CourseFactory()
        seat = course.create_or_update_seat('verified', True, 50, self.partner)
        _range = RangeFactory(products=[seat, ])
        prepare_voucher(code=COUPON_CODE, _range=_range)

        course_url = get_lms_url('api/courses/v1/courses/{}/'.format(course.id))
        httpretty.register_uri(httpretty.GET, course_url, status=404, content_type=CONTENT_TYPE)

        response = self.client.get(self.path_with_code)
        response_text = (
            'Could not get course information. '
            '[Client Error 404: http://127.0.0.1:8000/api/courses/v1/courses/{}/]'
        ).format(course.id)
        self.assertEqual(response.context['error'], _(response_text))

    def test_proper_code(self):
        """ Verify that proper information is returned when a valid code is provided. """
        _range = self.prepare_course_information()
        prepare_voucher(code=COUPON_CODE, _range=_range)
        response = self.client.get(self.path_with_code)
        self.assertEqual(response.context['course']['name'], _('Test course'))
        self.assertEqual(response.context['code'], COUPON_CODE)

    @ddt.data(
        (5, '45.00'),
        (100000, '0.00'),
    )
    @ddt.unpack
    def test_fixed_amount(self, benefit_value, new_price):
        """ Verify a new price is calculated properly with fixed price type benefit. """
        _range = self.prepare_course_information()
        prepare_voucher(code=COUPON_CODE, _range=_range, benefit_value=benefit_value, benefit_type=Benefit.FIXED_PRICE)
        response = self.client.get(self.path_with_code)
        self.assertEqual(response.context['new_price'], new_price)


class CouponRedeemViewTests(TestCase):
    redeem_url = reverse('coupons:redeem')

    def setUp(self):
        super(CouponRedeemViewTests, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)
        course = Course.objects.create(id='org/course/run')
        self.seat = course.create_or_update_seat('verified', True, 50, self.partner)

        self.catalog = Catalog.objects.create(partner=self.partner)
        self.catalog.stock_records.add(StockRecord.objects.get(product=self.seat))

    def create_and_test_coupon(self):
        """ Creates enrollment code coupon. """
        create_coupon(catalog=self.catalog, code=COUPON_CODE)
        self.assertEqual(Voucher.objects.filter(code=COUPON_CODE).count(), 1)

    def assert_redemption_page_redirects(self, expected_url, target=200):
        """ Verify redirect from redeem page to expected page. """
        url = self.redeem_url + '?code={}'.format(COUPON_CODE)
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
        response = self.client.get(self.redeem_url)
        self.assertEqual(response.context['error'], _('Code not provided'))

    def test_invalid_voucher(self):
        """ Verify a response message is returned when voucher does not exist. """
        url = self.redeem_url + '?code={}'.format('DOESNTEXIST')
        response = self.client.get(url)
        self.assertEqual(response.context['error'], _('Coupon does not exist'))

    def test_order_not_completed(self):
        """ Verify a response message is returned when an order is not completed. """
        self.create_and_test_coupon()
        url = self.redeem_url + '?code={}'.format(COUPON_CODE)
        response = self.client.get(url)
        self.assertEqual(response.context['error'], _('Error when trying to redeem code'))

    def test_basket_redirect_discount_code(self):
        """ Verify the view redirects to the basket single-item view when a discount code is provided. """
        create_coupon(catalog=self.catalog, code=COUPON_CODE, benefit_value=5)
        sku = StockRecord.objects.get(product=self.seat).partner_sku
        test_server_url = self.get_full_url(path=reverse('basket:single-item'))
        expected_url = '{url}?sku={sku}&code={code}'.format(url=test_server_url, sku=sku, code=COUPON_CODE)
        self.assert_redemption_page_redirects(expected_url, 303)

    @httpretty.activate
    def test_basket_redirect_enrollment_code(self):
        """ Verify the view redirects to LMS when an enrollment code is provided. """
        self.create_and_test_coupon()
        httpretty.register_uri(httpretty.POST, settings.ENROLLMENT_API_URL, status=200)
        self.assert_redemption_page_redirects(settings.LMS_URL_ROOT)

    @httpretty.activate
    def test_multiple_vouchers(self):
        """ Verify a redirect to LMS happens when a basket with already existing vouchers is used. """
        self.create_and_test_coupon()
        basket = Basket.get_basket(self.user, self.site)
        basket.vouchers.add(Voucher.objects.get(code=COUPON_CODE))
        httpretty.register_uri(httpretty.POST, settings.ENROLLMENT_API_URL, status=200)
        self.assert_redemption_page_redirects(settings.LMS_URL_ROOT)
