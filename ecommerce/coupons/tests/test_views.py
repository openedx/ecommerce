import datetime
from decimal import Decimal
import json

from django.conf import settings
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _
import httpretty
from oscar.core.loading import get_class, get_model
from oscar.test.factories import (OrderFactory, ConditionalOfferFactory, VoucherFactory,
                                  RangeFactory, BenefitFactory, ProductFactory)
from oscar.test.utils import RequestFactory
import pytz

from ecommerce.coupons.views import get_voucher, voucher_is_valid
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.tests.mixins import CouponMixin
from ecommerce.settings import get_lms_url
from ecommerce.tests.testcases import TestCase

Applicator = get_class('offer.utils', 'Applicator')
Basket = get_model('basket', 'Basket')
Catalog = get_model('catalogue', 'Catalog')
Course = get_model('courses', 'Course')
StockRecord = get_model('partner', 'StockRecord')
Voucher = get_model('voucher', 'Voucher')
VoucherApplication = get_model('voucher', 'VoucherApplication')


class CouponAppViewTests(CouponMixin, TestCase):
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


class CouponOfferViewTests(TestCase):
    offer_url = reverse('coupons:offer')

    def setUp(self):
        super(CouponOfferViewTests, self).setUp()

    def prepare_voucher(self, range_=None, start_datetime=None, benefit_value=100):
        """ Create a voucher and add an offer to it that contains a created product. """
        if range_ is None:
            product = ProductFactory(title='Test product')
            range_ = RangeFactory(products=[product, ])
        else:
            product = range_.all_products()[0]

        if start_datetime is None:
            start_datetime = now() - datetime.timedelta(days=1)

        voucher = VoucherFactory(code='COUPONTEST', start_datetime=start_datetime, usage=Voucher.SINGLE_USE)
        benefit = BenefitFactory(range=range_, value=benefit_value)
        offer = ConditionalOfferFactory(benefit=benefit)
        voucher.offers.add(offer)
        return voucher, product

    def test_get_voucher(self):
        """ Verify that get_voucher() returns product and voucher. """
        self.prepare_voucher()
        voucher, product = get_voucher(code='COUPONTEST')
        self.assertIsNotNone(voucher)
        self.assertEqual(voucher.code, 'COUPONTEST')
        self.assertIsNotNone(product)
        self.assertEqual(product.title, 'Test product')

    def test_no_product(self):
        """ Verify that None is returned if there is no product. """
        voucher = VoucherFactory(code='NOPRODUCT')
        offer = ConditionalOfferFactory()
        voucher.offers.add(offer)
        voucher, product = get_voucher(code='NOPRODUCT')
        self.assertIsNotNone(voucher)
        self.assertEqual(voucher.code, 'NOPRODUCT')
        self.assertIsNone(product)

    def test_get_non_existing_voucher(self):
        """ Verify that get_voucher() returns None for non-existing voucher. """
        voucher, product = get_voucher(code='INVALID')
        self.assertIsNone(voucher)
        self.assertIsNone(product)

    def test_valid_voucher(self):
        """ Verify voucher_is_valid() assess that the voucher is valid. """
        voucher, product = self.prepare_voucher()
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
        voucher, product = self.prepare_voucher(start_datetime=future_datetime)
        valid, msg = voucher_is_valid(voucher=voucher, product=product, request=None)
        self.assertFalse(valid)
        self.assertEqual(msg, _('Coupon expired'))

    def test_voucher_unavailable_to_buy(self):
        """ Verify that False is returned for unavialable products. """
        request = RequestFactory().request()
        voucher, product = self.prepare_voucher()
        product.expires = pytz.utc.localize(datetime.datetime.min)
        valid, __ = voucher_is_valid(voucher=voucher, product=product, request=request)
        self.assertFalse(valid)

    def test_used_voucher(self):
        """ Verify voucher_is_valid() assess that the voucher is unavailable. """
        voucher, product = self.prepare_voucher()
        order = OrderFactory()
        user = self.create_user()
        VoucherApplication.objects.create(voucher=voucher, user=user, order=order)
        request = RequestFactory().request()
        valid, msg = voucher_is_valid(voucher=voucher, product=product, request=request)
        self.assertFalse(valid)
        self.assertEqual(msg, _('This coupon has already been used'))

    def test_no_code(self):
        """ Verify a proper response is returned when no code is supplied. """
        response = self.client.get(self.offer_url)
        self.assertEqual(response.context['error'], _('This coupon code is invalid.'))

    def test_invalid_voucher(self):
        """ Verify a proper response is returned when voucher with provided code does not exist. """
        url = self.offer_url + '?code={}'.format('DOESNTEXIST')
        response = self.client.get(url)
        self.assertEqual(response.context['error'], _('Coupon does not exist'))

    @httpretty.activate
    def test_course_information_error(self):
        """ Verify a response is returned when course information is not accessable. """
        course = CourseFactory()
        seat = course.create_or_update_seat('verified', True, 50, self.partner)
        range_ = RangeFactory(products=[seat, ])
        self.prepare_voucher(range_=range_)

        course_url = get_lms_url('api/courses/v1/courses/{}/'.format(course.id))
        httpretty.register_uri(httpretty.GET, course_url, status=404, content_type='application/json')

        url = self.offer_url + '?code={}'.format('COUPONTEST')
        response = self.client.get(url)
        response_text = (
            'Could not get course information. '
            '[Client Error 404: http://127.0.0.1:8000/api/courses/v1/courses/{}/]'
        ).format(course.id)
        self.assertEqual(response.context['error'], _(response_text))

    @httpretty.activate
    def test_proper_code(self):
        """ Verify that proper information is returned when a valid code is provided. """
        course = CourseFactory()
        seat = course.create_or_update_seat('verified', True, 50, self.partner)
        sr = StockRecord.objects.get(product=seat)
        catalog = Catalog.objects.create(name='Test catalog', partner=self.partner)
        catalog.stock_records.add(sr)
        range_ = RangeFactory(catalog=catalog)
        self.prepare_voucher(range_=range_)

        course_info = {
            "media": {
                "course_image": {
                    "uri": "/asset-v1:edX+DemoX+Demo_Course+type@asset+block@images_course_image.jpg"
                }
            },
            "name": "edX Demonstration Course",
        }
        course_info_json = json.dumps(course_info)
        course_url = get_lms_url('api/courses/v1/courses/{}/'.format(course.id))
        httpretty.register_uri(httpretty.GET, course_url, body=course_info_json, content_type='application/json')

        url = self.offer_url + '?code={}'.format('COUPONTEST')
        response = self.client.get(url)
        self.assertEqual(response.context['course']['name'], _('edX Demonstration Course'))
        self.assertEqual(response.context['code'], _('COUPONTEST'))


class CouponRedeemViewTests(CouponMixin, TestCase):
    redeem_url = reverse('coupons:redeem')

    def setUp(self):
        super(CouponRedeemViewTests, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)
        course = Course.objects.create(id='org/course/run')
        self.seat = course.create_or_update_seat('verified', True, 50, self.partner)

        self.catalog = Catalog.objects.create(partner=self.partner)
        self.catalog.stock_records.add(StockRecord.objects.get(product=self.seat))

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

    def test_basket_not_free(self):
        """ Verify a response message is returned when the basket is not free. """
        self.assertEqual(StockRecord.objects.get(product=self.seat).price_excl_tax, Decimal('50.00'))
        self.create_coupon(catalog=self.catalog, code='COUPONTEST', benefit_value=0)
        url = self.redeem_url + '?code={}'.format('COUPONTEST')
        response = self.client.get(url)
        self.assertEqual(str(response.context['error']), _('Basket total not $0, current value = $50.00'))

    def test_order_not_completed(self):
        """ Verify a response message is returned when an order is not completed. """
        self.create_coupon(catalog=self.catalog, code='COUPONTEST')
        self.assertEqual(Voucher.objects.filter(code='COUPONTEST').count(), 1)

        url = self.redeem_url + '?code={}'.format('COUPONTEST')
        response = self.client.get(url)
        self.assertEqual(response.context['error'], _('Error when trying to redeem code'))

    @httpretty.activate
    def test_redirect(self):
        """ Verify a redirect happens when valid info is provided. """
        self.create_coupon(catalog=self.catalog, code='COUPONTEST')
        self.assertEqual(Voucher.objects.filter(code='COUPONTEST').count(), 1)

        httpretty.register_uri(httpretty.POST, settings.ENROLLMENT_API_URL, status=200)
        url = self.redeem_url + '?code={}'.format('COUPONTEST')
        response = self.client.get(url)
        self.assertIsInstance(response, HttpResponseRedirect)

    @httpretty.activate
    def test_multiple_vouchers(self):
        """ Verify a redirect happens when a basket with already existing vouchers is used. """
        self.create_coupon(catalog=self.catalog, code='COUPONTEST')
        self.assertEqual(Voucher.objects.filter(code='COUPONTEST').count(), 1)
        basket = Basket.get_basket(self.user, self.site)
        basket.vouchers.add(Voucher.objects.get(code='COUPONTEST'))
        httpretty.register_uri(httpretty.POST, settings.ENROLLMENT_API_URL, status=200)

        url = self.redeem_url + '?code={}'.format('COUPONTEST')
        response = self.client.get(url)
        self.assertIsInstance(response, HttpResponseRedirect)
