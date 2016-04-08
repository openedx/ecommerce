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

from ecommerce.core.models import SiteConfiguration
from ecommerce.core.tests import toggle_switch
from ecommerce.core.url_utils import get_lms_url
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.extensions.offer.utils import format_benefit_value
from ecommerce.extensions.payment.tests.processors import DummyProcessor
from ecommerce.extensions.test.factories import prepare_voucher
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


class BasketSingleItemViewTests(CouponMixin, CourseCatalogTestMixin, LmsApiMockMixin, TestCase):
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
        self.create_coupon(code=COUPON_CODE, benefit_value=5)

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
class BasketSummaryViewTests(CourseCatalogTestMixin, LmsApiMockMixin, TestCase):
    """ BasketSummaryView basket view tests. """
    path = reverse('basket:summary')

    def setUp(self):
        super(BasketSummaryViewTests, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)
        self.course = CourseFactory(name='BasketSummaryTest')
        site_configuration = SiteConfiguration.objects.get(site__id=1)

        old_payment_processors = site_configuration.payment_processors
        site_configuration.payment_processors = DummyProcessor.NAME
        site_configuration.save()

        def reset_site_config():
            """ Reset method - resets site_config to pre-test state """
            site_configuration.payment_processors = old_payment_processors
            site_configuration.save()

        self.addCleanup(reset_site_config)

        toggle_switch(settings.PAYMENT_PROCESSOR_SWITCH_PREFIX + DummyProcessor.NAME, True)

    def mock_course_api_error(self, error):
        def callback(request, uri, headers):  # pylint: disable=unused-argument
            raise error
        course_url = get_lms_url('api/courses/v1/courses/{}/'.format(self.course))
        httpretty.register_uri(httpretty.GET, course_url, body=callback, content_type='application/json')

    def create_basket_and_add_product(self, product):
        basket = factories.BasketFactory(owner=self.user, site=self.site)
        basket.add_product(product, 1)
        return basket

    def create_seat(self, course, seat_price=100, cert_type='verified'):
        return course.create_or_update_seat(cert_type, True, seat_price, self.partner)

    def create_and_apply_benefit_to_basket(self, basket, product, benefit_type, benefit_value):
        _range = factories.RangeFactory(products=[product, ])
        voucher, __ = prepare_voucher(_range=_range, benefit_type=benefit_type, benefit_value=benefit_value)
        basket.vouchers.add(voucher)
        Applicator().apply(basket)

    @ddt.data(ConnectionError, SlumberBaseException, Timeout)
    def test_course_api_failure(self, error):
        """ Verify a connection error and timeout are logged when they happen. """
        self.mock_footer_api_response()
        seat = self.create_seat(self.course)
        basket = self.create_basket_and_add_product(seat)
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
        (Benefit.PERCENTAGE, 100),
        (Benefit.PERCENTAGE, 50),
        (Benefit.FIXED, 50)
    )
    @ddt.unpack
    def test_response_success(self, benefit_type, benefit_value):
        """ Verify a successful response is returned. """
        seat = self.create_seat(self.course, 500)
        basket = self.create_basket_and_add_product(seat)
        self.create_and_apply_benefit_to_basket(basket, seat, benefit_type, benefit_value)

        self.assertEqual(basket.lines.count(), 1)
        self.mock_course_api_response(self.course)
        self.mock_footer_api_response()

        benefit, __ = Benefit.objects.get_or_create(type=benefit_type, value=benefit_value)

        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['lines']), 1)
        self.assertEqual(response.context['lines'][0].benefit_value, format_benefit_value(benefit))
        self.assertEqual(response.context['lines'][0].has_discount, True)
        self.assertEqual(response.context['payment_processors'][0].NAME, DummyProcessor.NAME)
        self.assertEqual(json.loads(response.context['footer']), {'footer': 'edX Footer'})

    def test_no_basket_response(self):
        """ Verify there are no lines in the context for a non-existing basket. """
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['lines'], [])

    def test_line_no_cert_type(self):
        seat = self.create_seat(course=self.course, cert_type='TEST', seat_price=100)
        self.create_basket_and_add_product(seat)
        response = self.client.get(self.path)
        self.assertIsNone(response.context['lines'][0].certificate_type)

    def test_line_item_discount_data(self):
        """ Verify that line item has correct discount data. """
        seat = self.create_seat(self.course)
        basket = self.create_basket_and_add_product(seat)
        self.create_and_apply_benefit_to_basket(basket, seat, Benefit.PERCENTAGE, 50)

        course_without_benefit = CourseFactory()
        seat_without_benefit = self.create_seat(course_without_benefit)
        basket.add_product(seat_without_benefit, 1)

        response = self.client.get(self.path)
        self.assertEqual(response.context['lines'][0].benefit_value, '50%')
        self.assertEqual(response.context['lines'][0].has_discount, True)

        self.assertEqual(response.context['lines'][1].benefit_value, None)
        self.assertEqual(response.context['lines'][1].has_discount, False)

    def test_cached_course(self):
        """ Verify that the course info is cached. """
        seat = self.create_seat(self.course, 50)
        basket = self.create_basket_and_add_product(seat)
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
