# -*- coding: utf-8 -*-
"""Unit tests of ecommerce API views."""
from collections import namedtuple
from decimal import Decimal
import json
import logging

import ddt
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.urlresolvers import reverse
from django.test import RequestFactory, TestCase, override_settings
import httpretty
import mock
from oscar.core.loading import get_model
from oscar.test import factories
from oscar.test.newfactories import ProductAttributeValueFactory
from rest_framework import status
from rest_framework.throttling import UserRateThrottle

from ecommerce.extensions.api import exceptions as api_exceptions
from ecommerce.extensions.api.constants import APIConstants as AC, APITrackingKeys as ATK
from ecommerce.extensions.api.serializers import OrderSerializer
from ecommerce.extensions.api.tests.test_authentication import AccessTokenMixin, OAUTH2_PROVIDER_URL
from ecommerce.extensions.api.v2.views import get_tracking_context
from ecommerce.extensions.payment import exceptions as payment_exceptions
from ecommerce.extensions.payment.processors import Cybersource
from ecommerce.extensions.payment.tests.processors import DummyProcessor, AnotherDummyProcessor
from ecommerce.tests.mixins import UserMixin, ThrottlingMixin, BasketCreationMixin


Basket = get_model('basket', 'Basket')


@ddt.ddt
@override_settings(
    FULFILLMENT_MODULES=['ecommerce.extensions.fulfillment.tests.modules.FakeFulfillmentModule']
)
class BasketCreateViewTests(BasketCreationMixin, ThrottlingMixin, TestCase):
    FREE_SKU = u'𝑭𝑹𝑬𝑬-𝑷𝑹𝑶𝑫𝑼𝑪𝑻'
    PAID_SKU = u'𝑷𝑨𝑰𝑫-𝑷𝑹𝑶𝑫𝑼𝑪𝑻'
    ALTERNATE_FREE_SKU = u'𝑨𝑳𝑻𝑬𝑹𝑵𝑨𝑻𝑬-𝑭𝑹𝑬𝑬-𝑷𝑹𝑶𝑫𝑼𝑪𝑻'
    ALTERNATE_PAID_SKU = u'𝑨𝑳𝑻𝑬𝑹𝑵𝑨𝑻𝑬-𝑷𝑨𝑰𝑫-𝑷𝑹𝑶𝑫𝑼𝑪𝑻'
    BAD_SKU = 'not-a-sku'
    UNAVAILABLE = False
    UNAVAILABLE_MESSAGE = 'Unavailable'
    FAKE_PROCESSOR_NAME = 'awesome-processor'

    def setUp(self):
        super(BasketCreateViewTests, self).setUp()

        # Override all loggers, suppressing logging calls of severity CRITICAL and below
        logging.disable(logging.CRITICAL)

        self.paid_product = factories.ProductFactory(
            structure='child',
            parent=self.base_product,
            title=u'𝐋𝐏 𝟓𝟔𝟎-𝟒',
            stockrecords__partner_sku=self.PAID_SKU,
            stockrecords__price_excl_tax=Decimal('180000.00'),
        )
        factories.ProductFactory(
            structure='child',
            parent=self.base_product,
            title=u'Papier-mâché',
            stockrecords__partner_sku=self.ALTERNATE_FREE_SKU,
            stockrecords__price_excl_tax=Decimal('0.00'),
        )
        factories.ProductFactory(
            structure='child',
            parent=self.base_product,
            title=u'𝐋𝐏 𝟓𝟕𝟎-𝟒 𝐒𝐮𝐩𝐞𝐫𝐥𝐞𝐠𝐠𝐞𝐫𝐚',
            stockrecords__partner_sku=self.ALTERNATE_PAID_SKU,
            stockrecords__price_excl_tax=Decimal('240000.00'),
        )

        # Remove logger override
        self.addCleanup(logging.disable, logging.NOTSET)

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

    def test_multiple_baskets(self):
        """Test that basket operations succeed if multiple editable baskets exist for the user."""
        User = get_user_model()
        user = User.objects.create_user(
            username=self.USER_DATA['username'],
        )

        # Create two editable baskets for the user
        for _ in xrange(2):
            basket = Basket(owner=user, status='Open')
            basket.save()

        response = self.create_basket(skus=[self.PAID_SKU], checkout=True)
        self.assertEqual(response.status_code, 200)

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
        request_data = {AC.KEYS.PRODUCTS: [{'not-sku': 'foo'}]}
        response = self.client.post(
            self.PATH,
            data=json.dumps(request_data),
            content_type='application/json',
            HTTP_AUTHORIZATION='JWT ' + self.generate_token(self.USER_DATA)
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
        token = self.generate_token(self.USER_DATA, secret=invalid_secret)
        response = self.create_basket(skus=[self.PAID_SKU], token=token)
        self.assertEqual(response.status_code, 401)

    def _bad_request_dict(self, developer_message, user_message):
        bad_request_dict = {
            'developer_message': developer_message,
            'user_message': user_message
        }
        return bad_request_dict


class RetrieveOrderViewTests(ThrottlingMixin, UserMixin, TestCase):
    """Test cases for getting existing orders. """

    def setUp(self):
        super(RetrieveOrderViewTests, self).setUp()

        user = self.create_user()
        self.order = factories.create_order(user=user)

        # Add a product attribute to one of the order items
        ProductAttributeValueFactory(product=self.order.lines.first().product)

        self.token = self.generate_jwt_token_header(user)

    @property
    def url(self):
        return reverse('api:v2:orders:retrieve', kwargs={'number': self.order.number})

    def test_get_order(self):
        """Test successful order retrieval."""
        response = self.client.get(self.url, HTTP_AUTHORIZATION=self.token)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, OrderSerializer(self.order).data)

    def test_order_wrong_user(self):
        """Test scenarios where an order should return a 404 due to the wrong user."""
        other_user = self.create_user()
        other_token = self.generate_jwt_token_header(other_user)
        response = self.client.get(self.url, HTTP_AUTHORIZATION=other_token)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class OrderByBasketRetrieveViewTests(RetrieveOrderViewTests):
    """Test cases for getting orders using the basket id. """

    @property
    def url(self):
        return reverse('api:v2:baskets:retrieve_order', kwargs={'basket_id': self.order.basket.id})


class OrderListViewTests(AccessTokenMixin, ThrottlingMixin, UserMixin, TestCase):
    def setUp(self):
        super(OrderListViewTests, self).setUp()
        self.path = reverse('api:v2:orders:list')
        self.user = self.create_user()
        self.token = self.generate_jwt_token_header(self.user)

    def test_not_authenticated(self):
        """ If the user is not authenticated, the view should return HTTP status 401. """
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 401)

    def assert_empty_result_response(self, response):
        """ Verifies that the view responded successfully with an empty result list. """
        self.assertEqual(response.status_code, 200)

        content = json.loads(response.content)
        self.assertEqual(content['count'], 0)
        self.assertEqual(content['results'], [])

    @httpretty.activate
    @override_settings(OAUTH2_PROVIDER_URL=OAUTH2_PROVIDER_URL)
    def test_access_token(self):
        """ Verifies that the view accepts OAuth2 access tokens for authentication."""
        auth_header = 'Bearer {}'.format(self.DEFAULT_TOKEN)

        self._mock_access_token_response(username=self.user.username)
        response = self.client.get(self.path, HTTP_AUTHORIZATION=auth_header)
        self.assert_empty_result_response(response)

    def test_no_orders(self):
        """ If the user has no orders, the view should return an empty list. """
        self.assertFalse(self.user.orders.exists())
        response = self.client.get(self.path, HTTP_AUTHORIZATION=self.token)
        self.assert_empty_result_response(response)

    def test_with_orders(self):
        """ The view should return a list of the user's orders, sorted reverse chronologically. """
        order = factories.create_order(user=self.user)
        response = self.client.get(self.path, HTTP_AUTHORIZATION=self.token)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)

        self.assertEqual(content['count'], 1)
        self.assertEqual(content['results'][0]['number'], unicode(order.number))

        # Test ordering
        order_2 = factories.create_order(user=self.user)
        response = self.client.get(self.path, HTTP_AUTHORIZATION=self.token)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)

        self.assertEqual(content['count'], 2)
        self.assertEqual(content['results'][0]['number'], unicode(order_2.number))
        self.assertEqual(content['results'][1]['number'], unicode(order.number))

    def test_with_other_users_orders(self):
        """ The view should only return orders for the authenticated users. """
        other_user = self.create_user()
        factories.create_order(user=other_user)
        response = self.client.get(self.path, HTTP_AUTHORIZATION=self.token)
        self.assert_empty_result_response(response)


class PaymentProcessorListViewTests(TestCase, UserMixin):
    """ Ensures correct behavior of the payment processors list view."""

    def setUp(self):
        self.token = self.generate_jwt_token_header(self.create_user())

        # Clear the view cache
        cache.clear()

    def assert_processor_list_matches(self, expected):
        """ DRY helper. """
        response = self.client.get(reverse('api:v2:payment:list_processors'), HTTP_AUTHORIZATION=self.token)
        self.assertEqual(response.status_code, 200)
        self.assertSetEqual(set(json.loads(response.content)), set(expected))

    def test_permission(self):
        """Ensure authentication is required to access the view. """
        response = self.client.get(reverse('api:v2:payment:list_processors'))
        self.assertEqual(response.status_code, 401)

    @override_settings(PAYMENT_PROCESSORS=['ecommerce.extensions.payment.tests.processors.DummyProcessor'])
    def test_get_one(self):
        """Ensure a single payment processor in settings is handled correctly."""
        self.assert_processor_list_matches([DummyProcessor.NAME])

    @override_settings(PAYMENT_PROCESSORS=[
        'ecommerce.extensions.payment.tests.processors.DummyProcessor',
        'ecommerce.extensions.payment.tests.processors.AnotherDummyProcessor',
    ])
    def test_get_many(self):
        """Ensure multiple processors in settings are handled correctly."""
        self.assert_processor_list_matches([DummyProcessor.NAME, AnotherDummyProcessor.NAME])


@ddt.ddt
class GetTrackingContextTests(TestCase):
    """ Ensures correct extraction of tracking metadata in API requests."""

    TEST_USER_ID = "test-user-id"
    TEST_CLIENT_ID = "test-client-id"

    @ddt.data(
        {ATK.LMS_USER_ID: TEST_USER_ID, ATK.LMS_CLIENT_ID: TEST_CLIENT_ID},
        {ATK.LMS_USER_ID: TEST_USER_ID},
        {ATK.LMS_CLIENT_ID: TEST_CLIENT_ID},
        {},
    )
    def test_get_tracking_context(self, tracking_data):
        """ When present in the request, values of recognized headers are set with correct keys in the context."""
        request_headers = {k.meta_key: v for k, v in tracking_data.items()}
        expected_context = {k.context_key: v for k, v in tracking_data.items()}
        request = RequestFactory().get('/foo', **request_headers)
        self.assertEqual(get_tracking_context(request), expected_context)
