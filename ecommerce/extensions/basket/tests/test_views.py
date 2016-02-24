import datetime
import hashlib
import json

import ddt
from django.conf import settings
from django.core.cache import cache
from django.core.urlresolvers import reverse
from django.test import override_settings
import httpretty
from oscar.core.loading import get_class, get_model
from oscar.test import newfactories as factories
import pytz
from requests.exceptions import ConnectionError, Timeout
from slumber.exceptions import SlumberBaseException
from testfixtures import LogCapture

from ecommerce.core.tests import toggle_switch
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.payment.tests.processors import DummyProcessor
from ecommerce.extensions.test.factories import prepare_voucher
from ecommerce.settings import get_lms_url
from ecommerce.tests.factories import StockRecordFactory
from ecommerce.tests.mixins import CouponMixin, LmsApiMockMixin
from ecommerce.tests.testcases import TestCase

Applicator = get_class('offer.utils', 'Applicator')
Basket = get_model('basket', 'Basket')
Benefit = get_model('offer', 'Benefit')
Catalog = get_model('catalogue', 'Catalog')
Selector = get_class('partner.strategy', 'Selector')
StockRecord = get_model('partner', 'StockRecord')

COUPON_CODE = 'COUPONTEST'


class BasketSingleItemViewTests(CouponMixin, LmsApiMockMixin, TestCase):
    """ BasketSingleItemView view tests. """
    path = reverse('basket:single-item')

    def setUp(self):
        super(BasketSingleItemViewTests, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)

        course = CourseFactory()
        course.create_or_update_seat('verified', True, 50, self.partner)
        product = course.create_or_update_seat('verified', False, 0, self.partner)
        self.stock_record = StockRecordFactory(product=product, partner=self.partner)
        self.catalog = Catalog.objects.create(partner=self.partner)
        self.catalog.stock_records.add(self.stock_record)

    def test_login_required(self):
        """ The view should redirect to login page if the user is not logged in. """
        self.client.logout()
        response = self.client.get(self.path)
        testserver_login_url = self.get_full_url(reverse('login'))
        expected_url = '{path}?next={basket_path}'.format(path=testserver_login_url, basket_path=self.path)
        self.assertRedirects(response, expected_url, target_status_code=302)

    def test_missing_sku(self):
        """ The view should return HTTP 400 if no SKU is provided. """
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content, 'No SKU provided.')

    def test_missing_product(self):
        """ The view should return HTTP 400 if SKU has no associated product. """
        sku = 'NONEXISTING'
        expected_content = 'SKU [{}] does not exist.'.format(sku)
        url = '{path}?sku={sku}'.format(path=self.path, sku=sku)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content, expected_content)

    def test_unavailable_product(self):
        """ The view should return HTTP 400 if the product is not available for purchase. """
        product = self.stock_record.product
        product.expires = pytz.utc.localize(datetime.datetime.min)
        product.save()
        self.assertFalse(Selector().strategy().fetch_for_product(product).availability.is_available_to_buy)

        expected_content = 'Product [{}] not available to buy.'.format(product.title)
        url = '{path}?sku={sku}'.format(path=self.path, sku=self.stock_record.partner_sku)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content, expected_content)

    @httpretty.activate
    def test_redirect_to_basket_summary(self):
        """
        Verify the view redirects to the basket summary page, and that the user's basket is prepared for checkout.
        """
        self.create_coupon(catalog=self.catalog, code=COUPON_CODE, benefit_value=5)

        self.mock_footer_api_response()
        self.mock_course_api_response()
        url = '{path}?sku={sku}&code={code}'.format(path=self.path, sku=self.stock_record.partner_sku,
                                                    code=COUPON_CODE)
        response = self.client.get(url)
        expected_url = self.get_full_url(reverse('basket:summary'))
        self.assertRedirects(response, expected_url, status_code=303)

        basket = Basket.objects.get(owner=self.user, site=self.site)
        self.assertEqual(basket.status, Basket.OPEN)
        self.assertEqual(basket.lines.count(), 1)
        self.assertTrue(basket.contains_a_voucher)
        self.assertEqual(basket.lines.first().product, self.stock_record.product)


@httpretty.activate
@ddt.ddt
@override_settings(PAYMENT_PROCESSORS=['ecommerce.extensions.payment.tests.processors.DummyProcessor'])
class BasketSummaryViewTests(LmsApiMockMixin, TestCase):
    """ BasketSummaryView basket view tests. """
    path = reverse('basket:summary')

    def setUp(self):
        super(BasketSummaryViewTests, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)
        self.course = CourseFactory(name='BasketSummaryTest')
        toggle_switch(settings.PAYMENT_PROCESSOR_SWITCH_PREFIX + DummyProcessor.NAME, True)

    def mock_course_api_error(self, error):
        def callback(request, uri, headers):  # pylint: disable=unused-argument
            raise error
        course_url = get_lms_url('api/courses/v1/courses/{}/'.format(self.course))
        httpretty.register_uri(httpretty.GET, course_url, body=callback, content_type='application/json')

    @ddt.data(ConnectionError, SlumberBaseException, Timeout)
    def test_course_api_failure(self, error):
        """ Verify a connection error and timeout are logged when they happen. """
        self.mock_footer_api_response()
        seat = self.course.create_or_update_seat('verified', True, 50, self.partner)
        basket = factories.BasketFactory(owner=self.user)
        basket.add_product(seat, 1)
        self.assertEqual(basket.lines.count(), 1)

        logger_name = 'ecommerce.extensions.basket.views'
        self.mock_course_api_error(error)

        with LogCapture(logger_name) as l:
            response = self.client.get(self.path)
            self.assertEqual(response.status_code, 200)
            l.check(
                (
                    logger_name, 'ERROR',
                    u'Failed to retrieve data from Course API for course [{}].'.format(self.course.id)
                )
            )

    @ddt.data(
        (Benefit.PERCENTAGE, 100, 100, False),
        (Benefit.PERCENTAGE, 50, 50, True),
        (Benefit.FIXED, 50, 10, True)
    )
    @ddt.unpack
    def test_response_success(self, benefit_type, benefit_value, expected_value, is_discounted):
        """ Verify a successful response is returned. """
        seat = self.course.create_or_update_seat('verified', True, 500, self.partner)
        basket = factories.BasketFactory(owner=self.user)
        basket.add_product(seat, 1)

        _range = factories.RangeFactory(products=[seat, ])
        voucher, __ = prepare_voucher(_range=_range, benefit_type=benefit_type, benefit_value=benefit_value)
        basket.vouchers.add(voucher)
        Applicator().apply(basket)

        self.assertEqual(basket.lines.count(), 1)
        self.mock_course_api_response(self.course)
        self.mock_footer_api_response()

        response = self.client.get(self.path)
        self.assertEqual(response.context['lines'][0].discount_percentage, expected_value)
        self.assertEqual(response.context['lines'][0].is_discounted, is_discounted)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['payment_processors'][0].NAME, DummyProcessor.NAME)
        self.assertEqual(json.loads(response.context['footer']), {'footer': 'edX Footer'})

    def test_cached_course(self):
        """ Verify that the course info is cached. """
        seat = self.course.create_or_update_seat('verified', True, 50, self.partner)
        basket = factories.BasketFactory(owner=self.user)
        basket.add_product(seat, 1)
        self.assertEqual(basket.lines.count(), 1)
        self.mock_course_api_response(self.course)
        self.mock_footer_api_response()

        cache_key = 'courses_api_detail_{}'.format(self.course.id)
        cache_hash = hashlib.md5(cache_key).hexdigest()
        cached_course_before = cache.get(cache_hash)
        self.assertIsNone(cached_course_before)

        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        cached_course_after = cache.get(cache_hash)
        self.assertEqual(cached_course_after['name'], self.course.name)
