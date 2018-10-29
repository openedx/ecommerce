import datetime
import hashlib
import urllib
from decimal import Decimal

import ddt
import httpretty
import mock
import pytz
from django.conf import settings
from django.contrib.messages import get_messages
from django.http import HttpResponseRedirect
from django.test import override_settings
from django.urls import reverse
from edx_django_utils.cache import TieredCache
from factory.fuzzy import FuzzyText
from oscar.apps.basket.forms import BasketVoucherForm
from oscar.core.loading import get_class, get_model
from oscar.test import factories
from oscar.test.utils import RequestFactory
from requests.exceptions import ConnectionError, Timeout
from slumber.exceptions import SlumberBaseException
from testfixtures import LogCapture
from waffle.testutils import override_flag

from ecommerce.core.exceptions import SiteConfigurationError
from ecommerce.core.tests import toggle_switch
from ecommerce.core.url_utils import get_lms_url
from ecommerce.coupons.tests.mixins import CouponMixin, DiscoveryMockMixin
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.enterprise.tests.mixins import EnterpriseServiceMockMixin
from ecommerce.entitlements.utils import create_or_update_course_entitlement
from ecommerce.extensions.analytics.utils import translate_basket_line_for_segment
from ecommerce.extensions.basket.constants import EMAIL_OPT_IN_ATTRIBUTE
from ecommerce.extensions.basket.tests.mixins import BasketMixin
from ecommerce.extensions.basket.utils import _set_basket_bundle_status
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
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
VoucherRemoveView = get_class('basket.views', 'VoucherRemoveView')

COUPON_CODE = 'COUPONTEST'
BUNDLE = 'bundle_identifier'


@ddt.ddt
class BasketAddItemsViewTests(
        CouponMixin, DiscoveryTestMixin, DiscoveryMockMixin, LmsApiMockMixin, BasketMixin, TestCase):
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

    def test_add_multiple_products_to_basket(self):
        """ Verify the basket accepts multiple products. """
        products = ProductFactory.create_batch(3, stockrecords__partner=self.partner)
        qs = urllib.urlencode({'sku': [product.stockrecords.first().partner_sku for product in products]}, True)
        url = '{root}?{qs}'.format(root=self.path, qs=qs)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 303)

        basket = response.wsgi_request.basket
        self.assertEqual(basket.status, Basket.OPEN)
        self.assertEqual(basket.lines.count(), len(products))

    def test_basket_with_utm_params(self):
        """ Verify the basket includes utm params after redirect. """
        products = ProductFactory.create_batch(3, stockrecords__partner=self.partner)
        qs = urllib.urlencode({'sku': [product.stockrecords.first().partner_sku for product in products]}, True)
        url = '{root}?{qs}&utm_source=test'.format(root=self.path, qs=qs)
        response = self.client.get(url)
        self.assertEqual(response.url, '/basket/?utm_source=test')

    def test_redirect_to_basket_summary(self):
        """
        Verify the view redirects to the basket summary page, and that the user's basket is prepared for checkout.
        """
        self.create_coupon(catalog=self.catalog, code=COUPON_CODE, benefit_value=5)

        self.mock_course_runs_endpoint(self.site_configuration.discovery_api_url, course_run=self.course)
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

    def test_add_multiple_products_no_skus_provided(self):
        """ Verify the Bad request exception is thrown when no skus are provided. """
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content, 'No SKUs provided.')

    def test_add_multiple_products_no_available_products(self):
        """ Verify the Bad request exception is thrown when no skus are provided. """
        response = self.client.get(self.path, data=[('sku', 1), ('sku', 2)])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content, 'Products with SKU(s) [1, 2] do not exist.')

    @ddt.data(Voucher.SINGLE_USE, Voucher.MULTI_USE)
    def test_add_multiple_products_and_use_voucher(self, usage):
        """ Verify the basket accepts multiple products and a single use voucher. """
        products = ProductFactory.create_batch(3, stockrecords__partner=self.partner)
        product_range = factories.RangeFactory(products=products)
        voucher, __ = prepare_voucher(_range=product_range, usage=usage)

        qs = urllib.urlencode({
            'sku': [product.stockrecords.first().partner_sku for product in products],
            'code': voucher.code
        }, True)
        url = '{root}?{qs}'.format(root=self.path, qs=qs)
        response = self.client.get(url)
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

        qs = urllib.urlencode({'sku': [product.stockrecords.first().partner_sku for product in [product1, product2]]},
                              True)
        url = '{root}?{qs}'.format(root=self.path, qs=qs)
        with mock.patch.object(UserAlreadyPlacedOrder, 'user_already_placed_order', return_value=True):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['error'], 'You have already purchased these products')

    def test_not_already_purchased_products(self):
        """
        Test user can purchase products which have not been already purchased
        """
        products = ProductFactory.create_batch(3, stockrecords__partner=self.partner)
        qs = urllib.urlencode({'sku': [product.stockrecords.first().partner_sku for product in products]}, True)
        url = '{root}?{qs}'.format(root=self.path, qs=qs)
        with mock.patch.object(UserAlreadyPlacedOrder, 'user_already_placed_order', return_value=False):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 303)

    def test_one_already_purchased_product(self):
        """
        Test prepare_basket removes already purchased product and checkout for the rest of products
        """
        order = create_order(site=self.site, user=self.user)
        products = ProductFactory.create_batch(3, stockrecords__partner=self.partner)
        products.append(OrderLine.objects.get(order=order).product)
        qs = urllib.urlencode({'sku': [product.stockrecords.first().partner_sku for product in products]}, True)
        url = '{root}?{qs}'.format(root=self.path, qs=qs)
        response = self.client.get(url)
        basket = response.wsgi_request.basket
        self.assertEqual(response.status_code, 303)
        self.assertEqual(basket.lines.count(), len(products) - 1)

    @mock.patch('ecommerce.enterprise.entitlements.get_entitlement_voucher')
    def test_with_entitlement_voucher(self, mock_get_entitlement_voucher):
        """
        The view ought to redirect to the coupon redemption flow, which is consent-aware.
        """
        voucher = mock_get_entitlement_voucher.return_value
        voucher.code = 'FAKECODE'
        sku = self.stock_record.partner_sku
        url = '{path}?{skus}'.format(path=self.path, skus=urllib.urlencode({'sku': [sku]}, doseq=True))
        response = self.client.get(url)

        expected_failure_url = (
            'http%3A%2F%2Ftestserver.fake%2Fbasket%2Fadd%2F%3Fconsent_failed%3DTrue%26sku%3D{sku}'.format(
                sku=sku
            )
        )

        expected_url = reverse('coupons:redeem') + '?code=FAKECODE&sku={sku}&failure_url={failure_url}'.format(
            sku=sku,
            failure_url=expected_failure_url,
        )
        self.assertRedirects(response, expected_url)

    @mock.patch('ecommerce.enterprise.entitlements.get_entitlement_voucher')
    def test_with_entitlement_voucher_consent_failed(self, mock_get_entitlement_voucher):
        """
        Since consent has already failed, we ought to follow the standard flow, rather than looping forever.
        """
        voucher = mock_get_entitlement_voucher.return_value
        voucher.code = 'FAKECODE'
        sku = self.stock_record.partner_sku
        url = '{path}?sku={sku}&consent_failed=true'.format(path=self.path, sku=sku)
        self.mock_course_runs_endpoint(self.site_configuration.discovery_api_url, course_run=self.course)
        response = self.client.get(url)
        expected_url = self.get_full_url(reverse('basket:summary'))
        self.assertRedirects(response, expected_url, status_code=303)

    def test_no_available_product(self):
        """ The view should return HTTP 400 if the product is not available for purchase. """
        product = self.stock_record.product
        product.expires = pytz.utc.localize(datetime.datetime.min)
        product.save()
        self.assertFalse(Selector().strategy().fetch_for_product(product).availability.is_available_to_buy)

        expected_content = 'No product is available to buy.'
        url = '{path}?sku={sku}'.format(path=self.path, sku=self.stock_record.partner_sku)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content, expected_content)

    def test_with_both_unavailable_and_available_products(self):
        """ Verify the basket ignores unavailable products and continue with available products. """
        products = ProductFactory.create_batch(3, stockrecords__partner=self.partner)

        products[0].expires = pytz.utc.localize(datetime.datetime.min)
        products[0].save()
        self.assertFalse(Selector().strategy().fetch_for_product(products[0]).availability.is_available_to_buy)

        qs = urllib.urlencode({
            'sku': [product.stockrecords.first().partner_sku for product in products],
        }, True)
        url = '{root}?{qs}'.format(root=self.path, qs=qs)
        response = self.client.get(url)
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
        url = '{path}?sku={sku}&email_opt_in={opt_in}'.format(
            path=self.path,
            sku=self.stock_record.partner_sku,
            opt_in=opt_in,
        )
        response = self.client.get(url)
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

        url = '{path}?sku={sku}'.format(
            path=self.path,
            sku=self.stock_record.partner_sku,
        )
        response = self.client.get(url)
        basket = response.wsgi_request.basket
        basket_attribute = BasketAttribute.objects.get(
            basket=basket,
            attribute_type=BasketAttributeType.objects.get(name=EMAIL_OPT_IN_ATTRIBUTE),
        )
        self.assertEqual(basket_attribute.value_text, 'False')


@httpretty.activate
@ddt.ddt
class BasketSummaryViewTests(EnterpriseServiceMockMixin, DiscoveryTestMixin, DiscoveryMockMixin, LmsApiMockMixin,
                             ApiMockMixin, BasketMixin, TestCase):
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

    def create_basket_and_add_product(self, product):
        basket = factories.BasketFactory(owner=self.user, site=self.site)
        basket.add_product(product, 1)
        return basket

    def create_seat(self, course, seat_price=100, cert_type='verified'):
        return course.create_or_update_seat(cert_type, True, seat_price)

    def create_and_apply_benefit_to_basket(self, basket, product, benefit_type, benefit_value):
        _range = factories.RangeFactory(products=[product, ])
        voucher, __ = prepare_voucher(_range=_range, benefit_type=benefit_type, benefit_value=benefit_value)
        basket.vouchers.add(voucher)
        Applicator().apply(basket)

    @ddt.data(ConnectionError, SlumberBaseException, Timeout)
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

        with LogCapture(logger_name) as l:
            response = self.client.get(self.path)
            self.assertEqual(response.status_code, 200)
            l.check(
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

        with mock.patch('ecommerce.extensions.basket.views.track_segment_event', return_value=(True, '')) as mock_track:
            response = self.client.get(self.path)

            # Verify events are sent to Segment
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

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['formset_lines_data']), 1)

        line_data = response.context['formset_lines_data'][0][1]
        self.assertEqual(line_data['benefit_value'], format_benefit_value(benefit))
        self.assertEqual(line_data['seat_type'], seat.attr.certificate_type.capitalize())
        self.assertEqual(line_data['product_title'], self.course.name)
        self.assertFalse(line_data['enrollment_code'])
        self.assertEqual(response.context['payment_processors'][0].NAME, DummyProcessor.NAME)

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

    def test_cached_course(self):
        """ Verify that the course info is cached. """
        seat = self.create_seat(self.course, 50)
        basket = self.create_basket_and_add_product(seat)
        self.mock_access_token_response()
        self.assertEqual(basket.lines.count(), 1)
        self.mock_course_run_detail_endpoint(
            self.course, discovery_api_url=self.site_configuration.discovery_api_url
        )

        cache_key = 'courses_api_detail_{}{}'.format(self.course.id, self.partner.short_code)
        cache_key = hashlib.md5(cache_key).hexdigest()
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
        self.assertEqual(line_data.get('image_url'), '')
        self.assertEqual(line_data.get('course_short_description'), None)

    @ddt.data(
        ('verified', True),
        ('credit', False)
    )
    @ddt.unpack
    def test_verification_message(self, cert_type, ver_req):
        """ Verify the variable for verification requirement is False for credit seats. """
        seat = self.create_seat(self.course, cert_type=cert_type)
        self.create_basket_and_add_product(seat)
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['display_verification_message'], ver_req)

    def test_verification_attribute_missing(self):
        """ Verify the variable for verification requirement is False when the attribute is missing. """
        seat = self.create_seat(self.course)
        ProductAttribute.objects.filter(name='id_verification_required').delete()
        self.create_basket_and_add_product(seat)
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['display_verification_message'], False)

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

    def test_order_details_entitlement_msg(self):
        """Verify the order details message is displayed for course entitlements."""

        product = create_or_update_course_entitlement(
            'verified', 100, self.partner, 'foo-bar', 'Foo Bar Entitlement')

        self.assert_order_details_in_context(product)

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
        testserver_login_url = self.get_full_url(reverse(settings.LOGIN_URL))
        expected_url = '{path}?next={next}'.format(path=testserver_login_url, next=urllib.quote(self.path))
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

    @httpretty.activate
    def test_free_basket_redirect(self):
        """
        Verify redirect to FreeCheckoutView when basket is free
        and an Enterprise-related offer is applied.
        """
        self.course_run.create_or_update_seat('verified', True, Decimal(10))
        self.create_basket_and_add_product(self.course_run.seat_products[0])
        self.prepare_enterprise_offer()

        response = self.client.get(self.path)

        self.assertRedirects(response, reverse('checkout:free-checkout'), fetch_redirect_response=False)

    def test_basket_offer_index_exception(self):
        """
        Test Basket offers index error is handled properly.
        # todo : Remove this test once LEARNER-6578 is resolved.
        """
        seat = self.create_seat(self.course)
        self.create_basket_and_add_product(seat)

        with mock.patch('ecommerce.extensions.basket.models.Line.has_discount', return_value=True):
            response = self.client.get(self.get_full_url(self.path))
        self.assertEqual(response.status_code, 200)


@httpretty.activate
class VoucherAddViewTests(LmsApiMockMixin, TestCase):
    """ Tests for VoucherAddView. """

    def setUp(self):
        super(VoucherAddViewTests, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)
        self.basket = factories.BasketFactory(owner=self.user, site=self.site)

        # Fallback storage is needed in tests with messages
        self.request.user = self.user
        self.request.basket = self.basket

        self.view = VoucherAddView()
        self.view.request = self.request

        self.form = BasketVoucherForm()
        self.form.cleaned_data = {'code': COUPON_CODE}

    def get_error_message_from_request(self):
        return list(get_messages(self.request))[-1].message

    def assert_form_valid_message(self, expected):
        """ Asserts the expected message is logged via messages framework when the
        view's form_valid method is called. """
        self.view.form_valid(self.form)

        actual = self.get_error_message_from_request()
        self.assertEqual(str(actual), expected)

    def test_no_voucher_error_msg(self):
        """ Verify correct error message is returned when voucher can't be found. """
        self.basket.add_product(ProductFactory())
        self.assert_form_valid_message("Coupon code '{code}' does not exist.".format(code=COUPON_CODE))

    def test_voucher_already_in_basket_error_msg(self):
        """ Verify correct error message is returned when voucher already in basket. """
        voucher, product = prepare_voucher(code=COUPON_CODE)
        self.basket.vouchers.add(voucher)
        self.basket.add_product(product)
        self.assert_form_valid_message(
            "You have already added coupon code '{code}' to your basket.".format(code=COUPON_CODE))

    def test_voucher_expired_error_msg(self):
        """ Verify correct error message is returned when voucher has expired. """
        self.mock_access_token_response()
        self.mock_account_api(self.request, self.user.username, data={'is_active': True})
        end_datetime = datetime.datetime.now() - datetime.timedelta(days=1)
        start_datetime = datetime.datetime.now() - datetime.timedelta(days=2)
        __, product = prepare_voucher(code=COUPON_CODE, start_datetime=start_datetime, end_datetime=end_datetime)
        self.basket.add_product(product)
        self.assert_form_valid_message("Coupon code '{code}' has expired.".format(code=COUPON_CODE))

    def test_voucher_added_to_basket_msg(self):
        """ Verify correct message is returned when voucher is added to basket. """
        self.mock_access_token_response()
        self.mock_account_api(self.request, self.user.username, data={'is_active': True})
        __, product = prepare_voucher(code=COUPON_CODE)
        self.basket.add_product(product)
        self.assert_form_valid_message("Coupon code '{code}' added to basket.".format(code=COUPON_CODE))

    def test_voucher_has_no_discount_error_msg(self):
        """ Verify correct error message is returned when voucher has no discount. """
        self.mock_access_token_response()
        self.mock_account_api(self.request, self.user.username, data={'is_active': True})
        __, product = prepare_voucher(code=COUPON_CODE, benefit_value=0)
        self.basket.add_product(product)
        self.assert_form_valid_message('Basket does not qualify for coupon code {code}.'.format(code=COUPON_CODE))

    def test_voucher_used_error_msg(self):
        """ Verify correct error message is returned when voucher has been used (Single use). """
        self.mock_access_token_response()
        self.mock_account_api(self.request, self.user.username, data={'is_active': True})
        voucher, product = prepare_voucher(code=COUPON_CODE)
        self.basket.add_product(product)
        order = factories.OrderFactory()
        VoucherApplication.objects.create(voucher=voucher, user=self.user, order=order)
        self.assert_form_valid_message("Coupon code '{code}' has already been redeemed.".format(code=COUPON_CODE))

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
            value_text='test_bundle'
        )
        self.assert_form_valid_message("Coupon code '{code}' is not valid for this basket.".format(code=voucher.code))

    def test_multi_use_voucher_valid_for_bundle(self):
        """ Verify multi use coupon works when voucher is used against a bundle. """
        self.mock_access_token_response()
        self.mock_account_api(self.request, self.user.username, data={'is_active': True})
        voucher, product = prepare_voucher(code=COUPON_CODE, benefit_value=10, usage=Voucher.MULTI_USE)
        new_product = factories.ProductFactory(categories=[], stockrecords__partner__short_code='second')
        self.basket.add_product(product)
        self.basket.add_product(new_product)
        _set_basket_bundle_status('test-bundle', self.basket)
        self.assert_form_valid_message("Coupon code '{code}' added to basket.".format(code=voucher.code))

    def test_form_valid_without_basket_id(self):
        """ Verify the view redirects to the basket summary view if the basket has no ID.  """
        self.request.basket = Basket()
        response = self.view.form_valid(self.form)
        self.assertEqual(response.url, reverse('basket:summary'))

    def test_inactive_voucher(self):
        """ Verify the view alerts the user if the voucher is inactive. """
        self.mock_access_token_response()
        self.mock_account_api(self.request, self.user.username, data={'is_active': True})
        code = FuzzyText().fuzz()
        start_datetime = datetime.datetime.now() + datetime.timedelta(days=1)
        end_datetime = start_datetime + datetime.timedelta(days=2)
        voucher, product = prepare_voucher(code=code, start_datetime=start_datetime, end_datetime=end_datetime)
        self.basket.add_product(product)
        self.form.cleaned_data = {'code': voucher.code}
        self.assert_form_valid_message("Coupon code '{code}' is not active.".format(code=voucher.code))

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
        resp = self.view.form_valid(self.form)
        self.assertIsInstance(resp, HttpResponseRedirect)

        stock_record = Selector().strategy().fetch_for_product(product).stockrecord

        expected_url_parts = (
            reverse('coupons:redeem'),
            'sku={sku}'.format(sku=stock_record.partner_sku),
            'code={code}'.format(code=COUPON_CODE),
            'failure_url=http%3A%2F%2F{domain}%2Fbasket%2F%3Fconsent_failed%3D{code}'.format(
                domain=self.site.domain,
                code=COUPON_CODE
            )
        )

        for part in expected_url_parts:
            self.assertIn(part, resp.url)

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

    def assert_account_activation_rendered(self):
        with self.assertTemplateUsed('edx/email_confirmation_required.html'):
            self.view.form_valid(self.form)

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

    def test_activation_not_required_for_inactive_user(self):
        self.mock_access_token_response()
        self.mock_account_api(self.request, self.user.username, data={'is_active': False})
        self.site.siteconfiguration.require_account_activation = False
        self.site.siteconfiguration.save()
        __, product = prepare_voucher(code=COUPON_CODE)
        self.basket.add_product(product)
        self.assert_form_valid_message("Coupon code '{code}' added to basket.".format(code=COUPON_CODE))


class VoucherRemoveViewTests(TestCase):
    def test_post_with_missing_voucher(self):
        """ If the voucher is missing, verify the view queues a message and redirects. """
        pk = '12345'
        view = VoucherRemoveView.as_view()
        request = RequestFactory().post('/')
        request.basket.save()
        response = view(request, pk=pk)

        self.assertEqual(response.status_code, 302)

        actual = list(get_messages(request))[-1].message
        expected = "No voucher found with id '{}'".format(pk)
        self.assertEqual(actual, expected)
