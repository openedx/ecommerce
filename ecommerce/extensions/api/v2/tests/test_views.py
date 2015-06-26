# -*- coding: utf-8 -*-
"""Unit tests of ecommerce API views."""
from collections import namedtuple
from decimal import Decimal
import json
import logging

import ddt
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.core.urlresolvers import reverse
from django.test import TestCase, override_settings
import httpretty
import mock
from oscar.core.loading import get_model
from oscar.test import factories
from oscar.test.newfactories import ProductAttributeValueFactory
from rest_framework import status
from rest_framework.throttling import UserRateThrottle
from testfixtures import LogCapture

from ecommerce.extensions.api import exceptions as api_exceptions
from ecommerce.extensions.api.constants import APIConstants as AC
from ecommerce.extensions.api.serializers import OrderSerializer, RefundSerializer
from ecommerce.extensions.api.tests.test_authentication import AccessTokenMixin, OAUTH2_PROVIDER_URL
from ecommerce.extensions.api.v2.views import BasketCreateView
from ecommerce.extensions.fulfillment.mixins import FulfillmentMixin
from ecommerce.extensions.fulfillment.status import LINE, ORDER
from ecommerce.extensions.payment import exceptions as payment_exceptions
from ecommerce.extensions.payment.processors.cybersource import Cybersource
from ecommerce.extensions.payment.tests.processors import DummyProcessor, AnotherDummyProcessor
from ecommerce.extensions.refund.tests.factories import RefundLineFactory, RefundFactory
from ecommerce.extensions.refund.tests.mixins import RefundTestMixin
from ecommerce.tests.mixins import UserMixin, ThrottlingMixin, BasketCreationMixin, JwtMixin

Basket = get_model('basket', 'Basket')
Order = get_model('order', 'Order')
ShippingEventType = get_model('order', 'ShippingEventType')
Refund = get_model('refund', 'Refund')
User = get_user_model()

JSON_CONTENT_TYPE = 'application/json'
LOGGER_NAME = 'ecommerce.extensions.api.v2.views'


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
            content_type=JSON_CONTENT_TYPE,
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

    @mock.patch.object(BasketCreateView, '_checkout', mock.Mock(side_effect=ValueError('Test message')))
    def test_checkout_exception(self):
        """ If an exception is raised when initiating the checkout process, a PaymentProcessorResponse should be
        recorded, and the view should return HTTP status 500. """

        with LogCapture(LOGGER_NAME, level=logging.ERROR) as l:
            response = self.create_basket(skus=[self.PAID_SKU], checkout=True)

            # Ensure the user's basket is thawed
            user = User.objects.get(username=self.USERNAME)
            basket = user.baskets.get()
            self.assertEqual(basket.status, Basket.OPEN)

            l.check((LOGGER_NAME, 'ERROR',
                     'Failed to initiate checkout for Basket [{}]. Basket has been thawed.'.format(basket.id)))

        # Validate the response status and content
        self.assertEqual(response.status_code, 500)
        actual = json.loads(response.content)
        expected = {
            'developer_message': 'Test message'
        }
        self.assertDictEqual(actual, expected)


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

    def test_super_user(self):
        """ The view should return all orders for when authenticating as a superuser. """
        superuser = self.create_user(is_superuser=True)
        order = factories.create_order(user=self.user)

        response = self.client.get(self.path, HTTP_AUTHORIZATION=self.generate_jwt_token_header(superuser))
        content = json.loads(response.content)
        self.assertEqual(content['count'], 1)
        self.assertEqual(content['results'][0]['number'], unicode(order.number))


@ddt.ddt
class OrderFulfillViewTests(UserMixin, TestCase):
    def setUp(self):
        super(OrderFulfillViewTests, self).setUp()
        ShippingEventType.objects.get_or_create(name=FulfillmentMixin.SHIPPING_EVENT_NAME)

        self.user = self.create_user(is_superuser=True)
        self.client.login(username=self.user.username, password=self.password)

        self.order = factories.create_order()
        self.order.status = ORDER.FULFILLMENT_ERROR
        self.order.save()
        self.order.lines.all().update(status=LINE.FULFILLMENT_CONFIGURATION_ERROR)

        self.url = reverse('api:v2:orders:fulfill', kwargs={'number': self.order.number})

    def _put_to_view(self):
        """
        PUT to the view being tested.

        Returns:
            Response
        """
        return self.client.put(self.url)

    @ddt.data('delete', 'get', 'post')
    def test_put_or_patch_required(self, method):
        """ Verify that the view only responds to PUT and PATCH operations. """
        response = getattr(self.client, method)(self.url)
        self.assertEqual(405, response.status_code)

    def test_login_required(self):
        """ The view should return HTTP 401 status if the user is not logged in. """
        self.client.logout()
        self.assertEqual(401, self._put_to_view().status_code)

    def test_change_permissions_required(self):
        """
        The view requires the user to have change permissions for Order objects. If the user does not have permission,
        the view should return HTTP 403 status.
        """
        self.user.is_superuser = False
        self.user.save()
        self.assertEqual(403, self._put_to_view().status_code)

        permission = Permission.objects.get(codename='change_order')
        self.user.user_permissions.add(permission)
        self.assertNotEqual(403, self._put_to_view().status_code)

    @ddt.data(ORDER.OPEN, ORDER.COMPLETE)
    def test_order_fulfillment_error_state_required(self, order_status):
        """ If the order is not in the Fulfillment Error state, the view must return an HTTP 406. """
        self.order.status = order_status
        self.order.save()
        self.assertEqual(406, self._put_to_view().status_code)

    def test_ideal_conditions(self):
        """
        If the user is authenticated/authorized, and the order is in the Fulfillment Error state, the view should
        attempt to fulfill the order. The view should return HTTP 200.
        """
        self.assertEqual(ORDER.FULFILLMENT_ERROR, self.order.status)

        with mock.patch('ecommerce.extensions.order.processing.EventHandler.handle_shipping_event') as mocked:
            def handle_shipping_event(order, _event_type, _lines, _line_quantities, **_kwargs):
                order.status = ORDER.COMPLETE
                order.save()
                return order

            mocked.side_effect = handle_shipping_event
            response = self._put_to_view()
            self.assertTrue(mocked.called)

        self.assertEqual(200, response.status_code)

        # Reload the order from the DB and check its status
        self.order = Order.objects.get(number=self.order.number)
        self.assertEqual(unicode(self.order.number), response.data['number'])
        self.assertEqual(self.order.status, response.data['status'])

    def test_fulfillment_failed(self):
        """ If fulfillment fails, the view should return HTTP 500. """
        self.assertEqual(ORDER.FULFILLMENT_ERROR, self.order.status)
        response = self._put_to_view()
        self.assertEqual(500, response.status_code)


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


class RefundCreateViewTests(RefundTestMixin, AccessTokenMixin, JwtMixin, UserMixin, TestCase):
    path = reverse('api:v2:refunds:create')

    def setUp(self):
        super(RefundCreateViewTests, self).setUp()
        self.course_id = 'edX/DemoX/Demo_Course'
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)

    def assert_bad_request_response(self, response, detail):
        """ Assert the response has status code 406 and the appropriate detail message. """
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = json.loads(response.content)
        self.assertEqual(data, {'detail': detail})

    def assert_ok_response(self, response):
        """ Assert the response has HTTP status 200 and no data. """
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(json.loads(response.content), [])

    def _get_data(self, username=None, course_id=None):
        data = {}

        if username:
            data['username'] = username

        if course_id:
            data['course_id'] = course_id

        return json.dumps(data)

    def test_no_orders(self):
        """ If the user has no orders, no refund IDs should be returned. HTTP status should be 200. """
        self.assertFalse(self.user.orders.exists())
        data = self._get_data(self.user.username, self.course_id)
        response = self.client.post(self.path, data, JSON_CONTENT_TYPE)
        self.assert_ok_response(response)

    def test_missing_data(self):
        """
        If course_id is missing from the POST body, return HTTP 400
        """
        data = self._get_data(self.user.username)
        response = self.client.post(self.path, data, JSON_CONTENT_TYPE)
        self.assert_bad_request_response(response, 'No course_id specified.')

    def test_user_not_found(self):
        """
        If no user matching the username is found, return HTTP 400.
        """
        superuser = self.create_user(is_superuser=True)
        self.client.login(username=superuser.username, password=self.password)

        username = 'fakey-userson'
        data = self._get_data(username, self.course_id)
        response = self.client.post(self.path, data, JSON_CONTENT_TYPE)
        self.assert_bad_request_response(response, 'User "{}" does not exist.'.format(username))

    def test_authentication_required(self):
        """ Clients MUST be authenticated. """
        self.client.logout()
        data = self._get_data(self.user.username, self.course_id)
        response = self.client.post(self.path, data, JSON_CONTENT_TYPE)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_jwt_authentication(self):
        """ Client can authenticate with JWT. """
        self.client.logout()

        data = self._get_data(self.user.username, self.course_id)
        auth_header = 'JWT ' + self.generate_token({'username': self.user.username})

        response = self.client.post(self.path, data, JSON_CONTENT_TYPE, HTTP_AUTHORIZATION=auth_header)
        self.assert_ok_response(response)

    @httpretty.activate
    @override_settings(OAUTH2_PROVIDER_URL=OAUTH2_PROVIDER_URL)
    def test_oauth_authentication(self):
        """ Client can authenticate with OAuth. """
        self.client.logout()

        data = self._get_data(self.user.username, self.course_id)
        auth_header = 'Bearer ' + self.DEFAULT_TOKEN
        self._mock_access_token_response(username=self.user.username)

        response = self.client.post(self.path, data, JSON_CONTENT_TYPE, HTTP_AUTHORIZATION=auth_header)
        self.assert_ok_response(response)

    def test_session_authentication(self):
        """ Client can authenticate with a Django session. """
        self.client.logout()
        self.client.login(username=self.user.username, password=self.password)

        data = self._get_data(self.user.username, self.course_id)
        response = self.client.post(self.path, data, JSON_CONTENT_TYPE)
        self.assert_ok_response(response)

    def test_authorization(self):
        """ Client must be authenticated as the user matching the username field or a superuser. """

        # A normal user CANNOT create refunds for other users.
        self.client.login(username=self.user.username, password=self.password)
        data = self._get_data('not-me', self.course_id)
        response = self.client.post(self.path, data, JSON_CONTENT_TYPE)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # A superuser can create refunds for everyone.
        superuser = self.create_user(is_superuser=True)
        self.client.login(username=superuser.username, password=self.password)
        data = self._get_data(self.user.username, self.course_id)
        response = self.client.post(self.path, data, JSON_CONTENT_TYPE)
        self.assert_ok_response(response)

    def test_valid_order(self):
        """
        View should create a refund if an order/line are found eligible for refund.
        """
        order = self.create_order()
        self.assertFalse(Refund.objects.exists())
        data = self._get_data(self.user.username, self.course_id)
        response = self.client.post(self.path, data, JSON_CONTENT_TYPE)
        refund = Refund.objects.latest()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(json.loads(response.content), [refund.id])
        self.assert_refund_matches_order(refund, order)

        # A second call should result in no additional refunds being created
        response = self.client.post(self.path, data, JSON_CONTENT_TYPE)
        self.assert_ok_response(response)

    def test_refunded_line(self):
        """
        View should NOT create a refund if an order/line is found, and has an existing refund.
        """
        order = self.create_order()
        Refund.objects.all().delete()
        RefundLineFactory(order_line=order.lines.first())
        self.assertEqual(Refund.objects.count(), 1)

        data = self._get_data(self.user.username, self.course_id)
        response = self.client.post(self.path, data, JSON_CONTENT_TYPE)
        self.assert_ok_response(response)
        self.assertEqual(Refund.objects.count(), 1)

    def test_non_course_order(self):
        """ Refunds should NOT be created for orders with no line items related to courses. """
        Refund.objects.all().delete()
        factories.create_order(user=self.user)
        self.assertEqual(Refund.objects.count(), 0)

        data = self._get_data(self.user.username, self.course_id)
        response = self.client.post(self.path, data, JSON_CONTENT_TYPE)

        self.assert_ok_response(response)
        self.assertEqual(Refund.objects.count(), 0)


@ddt.ddt
class RefundProcessViewTests(UserMixin, TestCase):
    def setUp(self):
        super(RefundProcessViewTests, self).setUp()

        self.user = self.create_user(is_staff=True)
        self.client.login(username=self.user.username, password=self.password)
        self.refund = RefundFactory(user=self.user)

    def put(self, action):
        data = '{{"action": "{}"}}'.format(action)
        path = reverse('api:v2:refunds:process', kwargs={'pk': self.refund.id})
        return self.client.put(path, data, JSON_CONTENT_TYPE)

    def test_staff_only(self):
        """ The view should only be accessible to staff users. """
        user = self.create_user(is_staff=False)
        self.client.login(username=user.username, password=self.password)
        response = self.put('approve')
        self.assertEqual(response.status_code, 403)

    def test_invalid_action(self):
        """ If the action is neither approve nor deny, the view should return HTTP 400. """
        response = self.put('reject')
        self.assertEqual(response.status_code, 400)

    @ddt.data('approve', 'deny')
    def test_success(self, action):
        """ If the action succeeds, the view should return HTTP 200 and the serialized Refund. """
        with mock.patch('ecommerce.extensions.refund.models.Refund.{}'.format(action), mock.Mock(return_value=True)):
            response = self.put(action)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, RefundSerializer(self.refund).data)

    @ddt.data('approve', 'deny')
    def test_failure(self, action):
        """ If the action fails, the view should return HTTP 500 and the serialized Refund. """
        with mock.patch('ecommerce.extensions.refund.models.Refund.{}'.format(action), mock.Mock(return_value=False)):
            response = self.put(action)
            self.assertEqual(response.status_code, 500)
            self.assertEqual(response.data, RefundSerializer(self.refund).data)
