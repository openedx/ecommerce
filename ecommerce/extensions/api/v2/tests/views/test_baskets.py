# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import datetime
import json
import urllib
from collections import namedtuple
from decimal import Decimal

import ddt
import httpretty
import mock
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from oscar.core.loading import get_model
from oscar.test import factories
from oscar.test.factories import BasketFactory
from rest_framework.throttling import UserRateThrottle
from waffle.testutils import override_flag, override_switch

from ecommerce.courses.models import Course
from ecommerce.extensions.api import exceptions as api_exceptions
from ecommerce.extensions.api.v2.tests.views import JSON_CONTENT_TYPE, OrderDetailViewTestMixin
from ecommerce.extensions.api.v2.views.baskets import BasketCalculateView, BasketCreateView
from ecommerce.extensions.payment import exceptions as payment_exceptions
from ecommerce.extensions.payment.processors.cybersource import Cybersource
from ecommerce.extensions.test.factories import (
    PercentageDiscountBenefitWithoutRangeFactory,
    ProgramCourseRunSeatsConditionFactory,
    ProgramOfferFactory,
    prepare_voucher
)
from ecommerce.programs.tests.mixins import ProgramTestMixin
from ecommerce.tests.factories import ProductFactory
from ecommerce.tests.mixins import BasketCreationMixin, ThrottlingMixin
from ecommerce.tests.testcases import TestCase, TransactionTestCase

Basket = get_model('basket', 'Basket')
Benefit = get_model('offer', 'Benefit')
ConditionalOffer = get_model('offer', 'ConditionalOffer')
Condition = get_model('offer', 'Condition')
Order = get_model('order', 'Order')
ShippingEventType = get_model('order', 'ShippingEventType')
Refund = get_model('refund', 'Refund')
User = get_user_model()
Voucher = get_model('voucher', 'Voucher')

LOGGER_NAME = 'ecommerce.extensions.api.v2.views.baskets'


@ddt.ddt
@override_settings(
    FULFILLMENT_MODULES=['ecommerce.extensions.fulfillment.tests.modules.FakeFulfillmentModule']
)
# Why TransactionTestCase? See http://stackoverflow.com/a/23326971.
class BasketCreateViewTests(BasketCreationMixin, ThrottlingMixin, TransactionTestCase):
    FREE_SKU = 'FREE_PRODUCT'
    PAID_SKU = 'PAID_PRODUCT'
    ALTERNATE_FREE_SKU = 'ALTERNATE_FREE_PRODUCT'
    ALTERNATE_PAID_SKU = 'ALTERNATE_PAID_PRODUCT'
    BAD_SKU = 'not-a-sku'
    UNAVAILABLE = False
    UNAVAILABLE_MESSAGE = 'Unavailable'
    FAKE_PROCESSOR_NAME = 'awesome-processor'

    def setUp(self):
        super(BasketCreateViewTests, self).setUp()

        self.paid_product = factories.ProductFactory(
            structure='child',
            parent=self.base_product,
            title='LP 560-4',
            stockrecords__partner_sku=self.PAID_SKU,
            stockrecords__price_excl_tax=Decimal('180000.00'),
            stockrecords__partner__short_code='oscr',
        )
        factories.ProductFactory(
            structure='child',
            parent=self.base_product,
            title=u'Papier-mâché',
            stockrecords__partner_sku=self.ALTERNATE_FREE_SKU,
            stockrecords__price_excl_tax=Decimal('0.00'),
            stockrecords__partner__short_code='otto',
        )
        factories.ProductFactory(
            structure='child',
            parent=self.base_product,
            title='LP 570-4 Superleggera',
            stockrecords__partner_sku=self.ALTERNATE_PAID_SKU,
            stockrecords__price_excl_tax=Decimal('240000.00'),
            stockrecords__partner__short_code='dummy',
        )

    @ddt.data(
        ([FREE_SKU], False, None, False),
        ([FREE_SKU], True, None, False),
        ([FREE_SKU, ALTERNATE_FREE_SKU], True, None, False),
        ([PAID_SKU], False, None, True),
        ([PAID_SKU], True, None, True),
        ([PAID_SKU], True, Cybersource.NAME, True),
        ([PAID_SKU, ALTERNATE_PAID_SKU], True, None, True),
        ([FREE_SKU, PAID_SKU], True, None, True),
    )
    @ddt.unpack
    def test_basket_creation_and_checkout(self, skus, checkout, payment_processor_name, requires_payment):
        """Test that a variety of product combinations can be added to the basket and purchased."""
        self.assert_successful_basket_creation(skus, checkout, payment_processor_name, requires_payment)

    @ddt.data(
        ([FREE_SKU], False),
        ([PAID_SKU], True),
    )
    @ddt.unpack
    def test_basket_creation_with_attribution(self, skus, requires_payment):
        """ Verify a basket is returned and referral method called. """
        with mock.patch('ecommerce.extensions.api.v2.views.baskets.attribute_cookie_data') as mock_attr_method:
            self.assert_successful_basket_creation(skus, False, None, requires_payment)
            self.assertTrue(mock_attr_method.called)

    def test_multiple_baskets(self):
        """ Test that basket operations succeed if the user has editable baskets. The endpoint should
        ALWAYS create a new basket. """
        # Create two editable baskets for the user
        basket_count = 2
        for _ in xrange(basket_count):
            basket = Basket(owner=self.user, status='Open')
            basket.save()

        self.assertEqual(self.user.baskets.count(), basket_count)
        response = self.create_basket(skus=[self.PAID_SKU], checkout=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user.baskets.count(), basket_count + 1)

    @mock.patch('oscar.apps.partner.strategy.Structured.fetch_for_product')
    def test_order_unavailable_product(self, mock_fetch_for_product):
        """Test that requests for unavailable products fail with appropriate messaging."""
        OrderInfo = namedtuple('OrderInfo', 'availability')
        Availability = namedtuple('Availability', ['is_available_to_buy', 'message'])

        order_info = OrderInfo(Availability(self.UNAVAILABLE, self.UNAVAILABLE_MESSAGE))
        mock_fetch_for_product.return_value = order_info

        response = self.create_basket(skus=[self.PAID_SKU])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            self._bad_request_dict(
                api_exceptions.PRODUCT_UNAVAILABLE_DEVELOPER_MESSAGE.format(
                    sku=self.PAID_SKU,
                    availability=self.UNAVAILABLE_MESSAGE
                ),
                api_exceptions.PRODUCT_UNAVAILABLE_USER_MESSAGE
            )
        )

    def test_product_objects_missing(self):
        """Test that requests without at least one product object fail with appropriate messaging."""
        response = self.create_basket()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            self._bad_request_dict(
                api_exceptions.PRODUCT_OBJECTS_MISSING_DEVELOPER_MESSAGE,
                api_exceptions.PRODUCT_OBJECTS_MISSING_USER_MESSAGE
            )
        )

    def test_sku_missing(self):
        """Test that requests without a SKU fail with appropriate messaging."""
        request_data = {'products': [{'not-sku': 'foo'}]}
        response = self.client.post(
            self.PATH,
            data=json.dumps(request_data),
            content_type=JSON_CONTENT_TYPE,
            HTTP_AUTHORIZATION=self.generate_jwt_token_header(self.user)
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            self._bad_request_dict(
                api_exceptions.SKU_NOT_FOUND_DEVELOPER_MESSAGE,
                api_exceptions.SKU_NOT_FOUND_USER_MESSAGE
            )
        )

    def test_no_product_for_sku(self):
        """Test that requests for non-existent products fail with appropriate messaging."""
        response = self.create_basket(skus=[self.BAD_SKU])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            self._bad_request_dict(
                api_exceptions.PRODUCT_NOT_FOUND_DEVELOPER_MESSAGE.format(sku=self.BAD_SKU),
                api_exceptions.PRODUCT_NOT_FOUND_USER_MESSAGE
            )
        )

    def test_no_payment_processor(self):
        """Test that requests for handling payment with a non-existent processor fail."""
        response = self.create_basket(
            skus=[self.PAID_SKU],
            checkout=True,
            payment_processor_name=self.FAKE_PROCESSOR_NAME
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            self._bad_request_dict(
                payment_exceptions.PROCESSOR_NOT_FOUND_DEVELOPER_MESSAGE.format(name=self.FAKE_PROCESSOR_NAME),
                payment_exceptions.PROCESSOR_NOT_FOUND_USER_MESSAGE
            )
        )

    def test_throttling(self):
        """Test that the rate of requests to the basket creation endpoint is throttled."""
        request_limit = UserRateThrottle().num_requests
        # Make a number of requests equal to the number of allowed requests
        for _ in xrange(request_limit):
            self.create_basket(skus=[self.PAID_SKU])

        # Make one more request to trigger throttling of the client
        response = self.create_basket(skus=[self.PAID_SKU])
        self.assertEqual(response.status_code, 429)
        self.assertIn("Request was throttled.", response.data['detail'])

    def test_jwt_authentication(self):
        """Test that requests made without a valid JWT fail."""
        # Verify that the basket creation endpoint requires JWT authentication
        response = self.create_basket(skus=[self.PAID_SKU], auth=False)
        self.assertEqual(response.status_code, 401)

        # Verify that the basket creation endpoint requires valid user data in the JWT payload
        token = self.generate_token({})
        response = self.create_basket(skus=[self.PAID_SKU], token=token)
        self.assertEqual(response.status_code, 401)

        # Verify that the basket creation endpoint requires user data to be signed with a valid secret;
        # guarantee an invalid secret by truncating the valid secret
        invalid_secret = self.JWT_SECRET_KEY[:-1]
        payload = {
            'username': self.user.username,
            'email': self.user.email,
        }
        token = self.generate_token(payload, secret=invalid_secret)
        response = self.create_basket(skus=[self.PAID_SKU], token=token)
        self.assertEqual(response.status_code, 401)

    def _bad_request_dict(self, developer_message, user_message):
        bad_request_dict = {
            'developer_message': developer_message,
            'user_message': user_message
        }
        return bad_request_dict

    @mock.patch.object(BasketCreateView, '_checkout', mock.Mock(side_effect=ValueError('Test message')))
    def test_checkout_exception(self):
        """ If an exception is raised when initiating the checkout process, a PaymentProcessorResponse should be
        recorded, and the view should return HTTP status 500. """

        self.user.baskets.all().delete()
        response = self.create_basket(skus=[self.PAID_SKU], checkout=True)

        # Verify no new basket was persisted to the database
        self.assertEqual(self.user.baskets.count(), 0)

        # Validate the response status and content
        self.assertEqual(response.status_code, 500)
        actual = json.loads(response.content)
        expected = {
            'developer_message': 'Test message'
        }
        self.assertDictEqual(actual, expected)


class OrderByBasketRetrieveViewTests(OrderDetailViewTestMixin, TestCase):
    """Test cases for getting orders using the basket id. """

    @property
    def url(self):
        return reverse('api:v2:baskets:retrieve_order', kwargs={'basket_id': self.order.basket.id})

    def test_deleted_basket(self):
        """ Verify the endpoint can retrieve an order even if the basket has been deleted. """
        url = self.url
        self.order.basket.delete()

        response = self.client.get(url, HTTP_AUTHORIZATION=self.token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.serialize_order(self.order))


class BasketDestroyViewTests(TestCase):
    def setUp(self):
        super(BasketDestroyViewTests, self).setUp()
        self.basket = BasketFactory()
        self.url = reverse('api:v2:baskets:destroy', kwargs={'basket_id': self.basket.id})

    def test_authorization(self):
        """ Verify regular users cannot delete baskets. """
        user = self.create_user()
        self.client.login(username=user.username, password=self.password)
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Basket.objects.filter(id=self.basket.id).exists())

    def test_deletion(self):
        """ Verify superusers can delete baskets. """
        superuser = self.create_user(is_superuser=True)
        self.client.login(username=superuser.username, password=self.password)
        response = self.client.delete(self.url)

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Basket.objects.filter(id=self.basket.id).exists())


class BasketCalculateViewTests(ProgramTestMixin, TestCase):
    def setUp(self):
        super(BasketCalculateViewTests, self).setUp()
        self.products = ProductFactory.create_batch(3, stockrecords__partner=self.partner, categories=[])
        self.path = reverse('api:v2:baskets:calculate')
        self.url = self._generate_sku_url(self.products)
        self.range = factories.RangeFactory(includes_all_products=True)
        self.product_total = sum(product.stockrecords.first().price_excl_tax for product in self.products)

        self.user = self._login_as_user(is_staff=True)

    def test_no_sku(self):
        """ Verify bad response when not providing sku(s) """
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 400)

    def test_invalid_sku(self):
        """ Verify bad response when sending an invalid sku """
        response = self.client.get(self.path + '?sku=foo')
        self.assertEqual(response.status_code, 400)

    def test_no_authentication(self):
        """ Verify that un-authenticated users are rejected """
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_basket_calculate_no_offers(self):
        """ Verify a successful basket calculation with no offers"""

        expected = {
            'total_incl_tax_excl_discounts': self.product_total,
            'total_incl_tax': self.product_total,
            'currency': 'GBP'
        }

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, expected)

    @httpretty.activate
    def test_basket_calculate_site_offer(self):
        """ Verify successful basket calculation with a site offer """

        discount_value = 10.00
        benefit = factories.BenefitFactory(type=Benefit.PERCENTAGE, range=self.range, value=discount_value)
        condition = factories.ConditionFactory(value=3, range=self.range, type=Condition.COVERAGE)
        factories.ConditionalOfferFactory(name='Test Offer', benefit=benefit, condition=condition,
                                          offer_type=ConditionalOffer.SITE,
                                          start_datetime=datetime.datetime.now() - datetime.timedelta(days=1),
                                          end_datetime=datetime.datetime.now() + datetime.timedelta(days=2))

        response = self.client.get(self.url)

        expected = {
            'total_incl_tax_excl_discounts': self.product_total,
            'total_incl_tax': Decimal('27.00'),
            'currency': 'GBP'
        }

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, expected)

    @httpretty.activate
    def test_basket_calculate_program_offer(self):
        """ Verify successful basket calculation with a program offer """
        offer = ProgramOfferFactory(
            site=self.site,
            benefit=PercentageDiscountBenefitWithoutRangeFactory(value=100)
        )
        program_uuid = offer.condition.program_uuid
        self.mock_program_detail_endpoint(program_uuid, self.site_configuration.discovery_api_url)
        self.mock_user_data(self.user.username)

        response = self.client.get(self.url)
        expected = {
            'total_incl_tax_excl_discounts': self.product_total,
            'total_incl_tax': self.product_total,
            'currency': 'GBP'
        }

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, expected)

    def test_basket_calculate_invalid_coupon(self):
        """ Verify successful basket calculation when passing an invalid voucher """
        response = self.client.get(self.url + '&code=foo')
        expected = {
            'total_incl_tax_excl_discounts': self.product_total,
            'total_incl_tax': self.product_total,
            'currency': 'GBP'
        }
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, expected)

    def test_basket_calculate_percentage_coupon(self):
        """ Verify successful basket calculation when passing a voucher """
        voucher, _ = prepare_voucher(_range=self.range)
        response = self.client.get(self.url + '&code={code}'.format(code=voucher.code))

        expected = {
            'total_incl_tax_excl_discounts': self.product_total,
            'total_incl_tax': Decimal('0.00'),
            'currency': 'GBP'
        }

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, expected)

    def test_basket_calculate_fixed_coupon(self):
        """ Verify successful basket calculation for a fixed price voucher """
        discount = 5
        voucher, _ = prepare_voucher(_range=self.range, benefit_type=Benefit.FIXED, benefit_value=discount)

        response = self.client.get(self.url + '&code={code}'.format(code=voucher.code))

        expected = {
            'total_incl_tax_excl_discounts': self.product_total,
            'total_incl_tax': self.product_total - discount,
            'currency': 'GBP'
        }

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, expected)

    @httpretty.activate
    def test_basket_calculate_by_staff_user_no_username(self):
        """Verify a staff user passing no username gets a response"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    @httpretty.activate
    @override_switch("debug_logging_for_excessive_lms_calls", active=True)
    def test_basket_calculate_by_staff_user_own_username(self):
        """Verify a staff user passing their own username gets a response about themself"""
        response = self.client.get(self.url + '&username={username}'.format(username=self.user.username))
        self.assertEqual(response.status_code, 200)

    @httpretty.activate
    @mock.patch('ecommerce.programs.conditions.ProgramCourseRunSeatsCondition._get_lms_resource_for_user')
    def test_basket_calculate_by_staff_user_own_username(self, mock_get_lms_resource_for_user):
        """Verify the marketing user passing own username gets an anonymous response"""
        self.site_configuration.enable_partial_program = True
        self.site_configuration.save()
        offer = ProgramOfferFactory(
            site=self.site,
            benefit=PercentageDiscountBenefitWithoutRangeFactory(value=100),
            condition=ProgramCourseRunSeatsConditionFactory()
        )
        program_uuid = offer.condition.program_uuid
        program = self.mock_program_detail_endpoint(program_uuid,
                                                    self.site_configuration.discovery_api_url)

        products = self._get_program_verified_seats(program)
        url = self._generate_sku_url(products, username=self.user.username)

        expected = {
            'total_incl_tax_excl_discounts': sum(
                product.stockrecords.first().price_excl_tax
                for product in products),
            'total_incl_tax': Decimal('0.00'),
            'currency': 'USD'
        }

        response = self.client.get(url)

        self.assertFalse(mock_get_lms_resource_for_user.called, msg='LMS calls should be skipped for anonymous case.')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, expected)

    @httpretty.activate
    @mock.patch('ecommerce.programs.conditions.ProgramCourseRunSeatsCondition._get_lms_resource_for_user')
    def test_basket_calculate_by_staff_user_other_username(self, mock_get_lms_resource_for_user):
        """Verify a staff user passing a valid username gets a response about the other user"""
        self.site_configuration.enable_partial_program = True
        self.site_configuration.save()
        offer = ProgramOfferFactory(
            site=self.site,
            benefit=PercentageDiscountBenefitWithoutRangeFactory(value=100),
            condition=ProgramCourseRunSeatsConditionFactory()
        )
        program_uuid = offer.condition.program_uuid
        program = self.mock_program_detail_endpoint(program_uuid, self.site_configuration.discovery_api_url)
        differentuser = self.create_user(username='differentuser', is_staff=False)

        products = self._get_program_verified_seats(program)
        url = self._generate_sku_url(products, username=differentuser.username)
        enrollment = [{'mode': 'verified', 'course_details': {'course_id': program['courses'][0]['key']}}]
        self.mock_user_data(differentuser.username, owned_products=enrollment)

        expected = {
            'total_incl_tax_excl_discounts': sum(product.stockrecords.first().price_excl_tax
                                                 for product in products),
            'total_incl_tax': Decimal('0.00'),
            'currency': 'USD'
        }

        response = self.client.get(url)

        # Note: This possibly should be in a test specifically around entitlements/enrollments.
        self.assertTrue(mock_get_lms_resource_for_user.called, msg='LMS calls should be made for non-anonymous case.')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, expected)

    @httpretty.activate
    @mock.patch('ecommerce.programs.conditions.ProgramCourseRunSeatsCondition._get_lms_resource_for_user')
    @override_flag("use_basket_calculate_none_user", active=True)
    @override_switch("debug_logging_for_excessive_lms_calls", active=True)
    def test_basket_calculate_anonymous_skip_lms(self, mock_get_lms_resource_for_user):
        """Verify a call for an anonymous user skips calls to LMS for entitlements and enrollments"""
        products, url = self.setup_anonymous_basket_calculate()

        expected = {
            'total_incl_tax_excl_discounts': sum(product.stockrecords.first().price_excl_tax
                                                 for product in products),
            'total_incl_tax': Decimal('0.00'),
            'currency': 'USD'
        }

        response = self.client.get(url)

        self.assertFalse(mock_get_lms_resource_for_user.called, msg='LMS calls should be skipped for anonymous case.')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, expected)

    @httpretty.activate
    @mock.patch('ecommerce.programs.conditions.ProgramCourseRunSeatsCondition._get_lms_resource_for_user')
    @override_flag("use_basket_calculate_none_user", active=False)
    def test_basket_calculate_anonymous_calls_lms(self, mock_get_lms_resource_for_user):
        """
        Verify a call for an anonymous user does not skip calls to LMS for entitlements and enrollments
        when waffle flag is not set.
        """
        products, url = self.setup_anonymous_basket_calculate()

        expected = {
            'total_incl_tax_excl_discounts': sum(product.stockrecords.first().price_excl_tax
                                                 for product in products),
            'total_incl_tax': Decimal('0.00'),
            'currency': 'USD'
        }

        response = self.client.get(url)

        self.assertTrue(mock_get_lms_resource_for_user.called, msg='LMS calls should be skipped for anonymous case.')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, expected)

    def setup_anonymous_basket_calculate(self):
        """
        Sets up anonymous basket calculate.

        Side Effects:
            Logs in the Marketing User, required for anonymous baskets at this time.

        Returns:
            products, url: The product list and the url for the anonymous basket
                calculate.
        """
        self._login_as_user(BasketCalculateView.MARKETING_USER, is_staff=True)
        self.site_configuration.enable_partial_program = True
        self.site_configuration.save()
        offer = ProgramOfferFactory(
            site=self.site,
            benefit=PercentageDiscountBenefitWithoutRangeFactory(value=100),
            condition=ProgramCourseRunSeatsConditionFactory()
        )
        program_uuid = offer.condition.program_uuid
        program = self.mock_program_detail_endpoint(
            program_uuid, self.site_configuration.discovery_api_url
        )
        products = self._get_program_verified_seats(program)
        url = self._generate_sku_url(products, username=None)
        return products, url

    @httpretty.activate
    @mock.patch('ecommerce.extensions.api.v2.views.baskets.BasketCalculateView._calculate_temporary_basket')
    @override_flag("use_cached_basket_calculate_for_marketing_user", active=True)
    def test_basket_calculate_anonymous_caching(self, mock_calculate_basket):
        """Verify a request made by the Marketing Staff user is cached"""
        self._login_as_user(BasketCalculateView.MARKETING_USER, is_staff=True)

        url_with_one_sku = self._generate_sku_url(self.products, number_of_products=1, username=None)
        url_with_two_skus = self._generate_sku_url(self.products, number_of_products=2, username=None)

        expected = {'Test Succeeded': True}
        mock_calculate_basket.return_value = {'Test Succeeded': True}

        # Call BasketCalculate. The cache should not be hit.
        response = self.client.get(url_with_one_sku)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(mock_calculate_basket.called, msg='The cache should be missed.')
        self.assertEqual(response.data, expected)

        mock_calculate_basket.reset_mock()

        # Call BasketCalculate again to test that we get the Cached response
        response = self.client.get(url_with_one_sku)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(mock_calculate_basket.called, msg='The cache should be hit.')
        self.assertEqual(response.data, expected)

        mock_calculate_basket.reset_mock()

        # Check that setting the username parameter doesn't hit the cache
        url_with_different_username = self._generate_sku_url(self.products, username="different_user")

        response = self.client.get(url_with_different_username)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(mock_calculate_basket.called, msg='The cache should be missed.')
        self.assertEqual(response.data, expected)

        mock_calculate_basket.reset_mock()

        # Check that a different set of skus does not hit cache
        response = self.client.get(url_with_two_skus)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(mock_calculate_basket.called, msg='The cache should be missed.')
        self.assertEqual(response.data, expected)

        mock_calculate_basket.reset_mock()

        # Check that a being logged in as a different user doesn't hit the cache
        self._login_as_user('different_user', is_staff=False)
        previous_cached_url = url_with_one_sku
        response = self.client.get(previous_cached_url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(mock_calculate_basket.called, msg='The cache should be missed.')
        self.assertEqual(response.data, expected)

    @httpretty.activate
    @mock.patch('ecommerce.extensions.api.v2.views.baskets.BasketCalculateView._calculate_temporary_basket')
    @override_flag("use_cached_basket_calculate_for_marketing_user", active=False)
    def test_basket_calculate_with_anonymous_caching_disabled(self, mock_calculate_basket):
        """Verify a request made by the Marketing Staff user is not cached"""
        self._login_as_user(BasketCalculateView.MARKETING_USER, is_staff=True)

        expected = {'Test Succeeded': True}
        mock_calculate_basket.return_value = {'Test Succeeded': True}

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(mock_calculate_basket.called)
        self.assertEqual(response.data, expected)

        mock_calculate_basket.reset_mock()

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(mock_calculate_basket.called, msg='The cache should be missed.')
        self.assertEqual(response.data, expected)

    @httpretty.activate
    @mock.patch('ecommerce.programs.conditions.ProgramCourseRunSeatsCondition._get_lms_resource_for_user')
    @mock.patch('ecommerce.extensions.api.v2.views.baskets.logger.exception')
    def test_basket_calculate_by_staff_user_invalid_username(self, mocked_logger, mock_get_lms_resource_for_user):
        """Verify that a staff user passing an invalid username gets the anonymous
           value and an error is logged about a non existent user """
        self.site_configuration.enable_partial_program = True
        self.site_configuration.save()
        offer = ProgramOfferFactory(
            site=self.site,
            benefit=PercentageDiscountBenefitWithoutRangeFactory(value=100),
            condition=ProgramCourseRunSeatsConditionFactory()
        )
        program_uuid = offer.condition.program_uuid
        program = self.mock_program_detail_endpoint(program_uuid, self.site_configuration.discovery_api_url)
        differentuser = self.create_user(username='differentuser', is_staff=False)

        products = self._get_program_verified_seats(program)
        url = self._generate_sku_url(products, username='invalidusername')
        enrollment = [{'mode': 'verified', 'course_details': {'course_id': program['courses'][0]['key']}}]
        self.mock_user_data(differentuser.username, enrollment)

        expected = {
            'total_incl_tax_excl_discounts': sum(product.stockrecords.first().price_excl_tax
                                                 for product in products[1:]),
            'total_incl_tax': Decimal('300.00'),
            'currency': 'USD'
        }

        with self.assertRaises(Exception):
            response = self.client.get(url)

            self.assertTrue(mock_get_lms_resource_for_user.called, msg='LMS calls should be skipped for anonymous case.')

            self.assertEqual(response.status_code, 200)
            self.assertTrue(mocked_logger.called)
            self.assertEqual(response.data, expected)

    @httpretty.activate
    def test_basket_calculate_username_by_nonstaff_user_own_username(self):
        """Verify a non-staff user passing their own username gets a valid response"""
        nonstaffuser = self.create_user(is_staff=False)
        self.request.user = nonstaffuser
        self.client.login(username=nonstaffuser.username, password=self.password)
        response = self.client.get(self.url + '&username={username}'.format(username=nonstaffuser.username))
        self.assertEqual(response.status_code, 200)

    @httpretty.activate
    def test_basket_calculate_by_nonstaff_user_other_username(self):
        """Verify a non-staff user passing a different username is forbidden"""
        nonstaffuser = self.create_user(is_staff=False)
        differentuser = self.create_user(username='ImDifferentYeahImDifferent', is_staff=False)
        self.request.user = nonstaffuser
        self.client.login(username=nonstaffuser.username, password=self.password)
        response = self.client.get(self.url + '&username={username}'.format(username=differentuser.username))
        self.assertEqual(response.status_code, 403)

    @mock.patch('ecommerce.extensions.basket.models.Basket.add_product', mock.Mock(side_effect=Exception))
    @mock.patch('ecommerce.extensions.api.v2.views.baskets.logger.exception')
    def test_exception_log(self, mocked_logger):
        """A log entry is filed when an exception happens."""
        voucher, _ = prepare_voucher(_range=self.range, benefit_type=Benefit.FIXED, benefit_value=5)

        with self.assertRaises(Exception):
            self.client.get(self.url + '&code={code}'.format(code=voucher.code))
            self.assertTrue(mocked_logger.called)

    @mock.patch('ecommerce.extensions.api.v2.views.baskets.get_entitlement_voucher')
    def test_basket_calculate_entitlement_voucher(self, mock_get_entitlement_voucher):
        """ Verify successful basket calculation considering Enterprise entitlement vouchers """

        discount = 5
        # Using ONCE_PER_CUSTOMER usage here because it fully excercises the Oscar Applicator code.
        voucher, _ = prepare_voucher(_range=self.range, benefit_type=Benefit.FIXED, benefit_value=discount,
                                     usage=Voucher.ONCE_PER_CUSTOMER)
        mock_get_entitlement_voucher.return_value = voucher

        # If the list of sku's contains more than one product no entitlement voucher is applied
        response = self.client.get(self.url)

        expected = {
            'total_incl_tax_excl_discounts': self.product_total,
            'total_incl_tax': self.product_total,
            'currency': 'GBP'
        }

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, expected)

        # If it's only one product, the entitlement voucher is applied
        product = self.products[0]
        url = self._generate_sku_url(self.products, 1)
        product_total = product.stockrecords.first().price_excl_tax

        response = self.client.get(url)

        expected = {
            'total_incl_tax_excl_discounts': product_total,
            'total_incl_tax': product_total - discount,
            'currency': 'GBP'
        }

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, expected)

    def _generate_sku_url(self, products, number_of_products=None, username=None):
        """
        Generates the calculate basket view's url for the given products

        Args:
            products (list): A list of products
            number_of_products (int): Number of given products to add in the url
            username (string, optional): Username to add in the url
        Returns:
            (string): Url with product skus and username appended as parameters

        """
        if not number_of_products:
            number_of_products = len(products)
        qs = urllib.urlencode(
            {'sku': [product.stockrecords.first().partner_sku for product in products[:number_of_products]]},
            True
        )
        url = '{root}?{qs}'.format(root=self.path, qs=qs)
        if username:
            url += '&username={username}'.format(username=username)
        return url

    def _get_program_verified_seats(self, program):
        products = []
        for course in program['courses']:
            course_run = Course.objects.get(id=course['course_runs'][0]['key'])
            for seat in course_run.seat_products:
                if seat.attr.certificate_type == 'verified':
                    products.append(seat)
        return products

    def _login_as_user(self, username=None, is_staff=False):
        user = self.create_user(
            username=username,
            is_staff=is_staff
        )

        self.client.logout()
        self.client.login(username=user.username, password=self.password)
        return user
