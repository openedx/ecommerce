# -*- coding: utf-8 -*-
"""Unit tests of the orders view."""
import json
import logging
from decimal import Decimal as D
from collections import namedtuple

import ddt
import httpretty
import jwt
import mock
from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.urlresolvers import reverse
from django.test import TestCase, override_settings
from nose.tools import raises
from oscar.test import factories
from oscar.core.loading import get_model
from rest_framework import status

from ecommerce.extensions.api import errors, data
from ecommerce.extensions.api.serializers import OrderSerializer
from ecommerce.extensions.api.tests.test_authentication import AccessTokenMixin, OAUTH2_PROVIDER_URL
from ecommerce.extensions.api.views import OrdersThrottle, FulfillmentMixin, OrderListCreateAPIView
from ecommerce.extensions.fulfillment.status import LINE, ORDER
from ecommerce.extensions.order.utils import OrderNumberGenerator
from ecommerce.tests.mixins import UserMixin


Order = get_model('order', 'Order')
Basket = get_model('basket', 'Basket')
ShippingEventType = get_model('order', 'ShippingEventType')


class ThrottlingMixin(object):
    def setUp(self):
        super(ThrottlingMixin, self).setUp()

        # Throttling for tests relies on the cache. To get around throttling, simply clear the cache.
        cache.clear()


@ddt.ddt
class RetrieveOrderViewTests(ThrottlingMixin, UserMixin, TestCase):
    """Test cases for getting existing orders. """

    def setUp(self):
        super(RetrieveOrderViewTests, self).setUp()
        user = self.create_user()
        basket = factories.create_basket()
        order_number = OrderNumberGenerator.order_number(basket)
        self.order = factories.create_order(number=order_number)
        self.order.status = ORDER.PAID
        self.order.user = user
        self.order.save()

        self.token = self.generate_jwt_token_header(user)
        self.url = reverse('orders:retrieve', kwargs={'number': self.order.number})

    @ddt.data(ORDER.PAID, ORDER.COMPLETE, ORDER.REFUNDED, ORDER.FULFILLMENT_ERROR)
    def test_get_order(self, order_status):
        """Test all scenarios where an order should be successfully retrieved. """
        self.order.status = order_status
        self.order.save()
        response = self.client.get(self.url, HTTP_AUTHORIZATION=self.token)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result_order = json.loads(response.content)
        self.assertEqual(OrderSerializer(self.order).data, result_order)

    @ddt.data(ORDER.OPEN, ORDER.BEING_PROCESSED, ORDER.ORDER_CANCELLED, ORDER.PAYMENT_CANCELLED)
    def test_order_not_found(self, order_status):
        """Test all scenarios where an order should return a 404 due to unpaid state. """
        self.order.status = order_status
        self.order.save()
        response = self.client.get(self.url, HTTP_AUTHORIZATION=self.token)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_order_wrong_user(self):
        """Test all scenarios where an order should return a 404 due to the wrong user. """
        other_user = self.create_user()
        other_token = self.generate_jwt_token_header(other_user)
        response = self.client.get(self.url, HTTP_AUTHORIZATION=other_token)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class CreateOrderViewTests(TestCase):
    USER_DATA = {
        'username': 'sgoodman',
        'email': 'saul@bettercallsaul.com',
    }
    EXPENSIVE_TRIAL_SKU = u'ṔŔíVÁTÉ-ÁTTŐŔŃÉӲ'
    FREE_TRIAL_SKU = u'ṖÜḄḶЇĊ⸚ḊЁḞЁṄḊЁṚ'
    SHIPPING_EVENT_NAME = OrderListCreateAPIView.SHIPPING_EVENT_NAME
    NONEXISTENT_SHIPPING_EVENT_NAME = 'Not Shipping'
    UNAVAILABLE = False
    UNAVAILABLE_MESSAGE = 'Unavailable'
    JWT_SECRET_KEY = getattr(settings, 'JWT_AUTH')['JWT_SECRET_KEY']

    def setUp(self):
        # Override all loggers, suppressing logging calls of severity CRITICAL and below
        logging.disable(logging.CRITICAL)

        self.product_class = factories.ProductClassFactory(
            name=u'𝕿𝖗𝖎𝖆𝖑',
            requires_shipping=False,
            track_stock=False
        )
        self.courthouse = factories.ProductFactory(
            structure='parent',
            title=u'𝑩𝒆𝒓𝒏𝒂𝒍𝒊𝒍𝒍𝒐 𝑪𝒐𝒖𝒏𝒕𝒚 𝑨𝒏𝒏𝒆𝒙',
            product_class=self.product_class,
            stockrecords=None,
        )
        self.expensive_trial = factories.ProductFactory(
            structure='child',
            parent=self.courthouse,
            title=u'𝕋𝕣𝕚𝕒𝕝 𝕨𝕚𝕥𝕙 ℙ𝕣𝕚𝕧𝕒𝕥𝕖 𝔸𝕥𝕥𝕠𝕣𝕟𝕖𝕪',
            product_class=self.product_class,
            stockrecords__partner_sku=self.EXPENSIVE_TRIAL_SKU,
            stockrecords__price_excl_tax=D('999.99'),
        )

        # Remove logger override
        self.addCleanup(logging.disable, logging.NOTSET)

    def test_order_paid_product(self):
        """Test that products with a non-zero price can be ordered successfully."""
        self._create_and_verify_order(self.EXPENSIVE_TRIAL_SKU, self.SHIPPING_EVENT_NAME)

    @mock.patch.object(OrderListCreateAPIView, '_fulfill_order', mock.Mock(side_effect=lambda order: order))
    def test_order_free_product(self):
        """Test that free products can be ordered successfully."""
        factories.ProductFactory(
            structure='child',
            parent=self.courthouse,
            title=u'𝕋𝕣𝕚𝕒𝕝 𝕨𝕚𝕥𝕙 ℙ𝕦𝕓𝕝𝕚𝕔 𝔻𝕖𝕗𝕖𝕟𝕕𝕖𝕣',
            product_class=self.product_class,
            stockrecords__partner_sku=self.FREE_TRIAL_SKU,
            stockrecords__price_excl_tax=D('0.00'),
        )

        self._create_and_verify_order(self.FREE_TRIAL_SKU, self.SHIPPING_EVENT_NAME)

    def test_order_with_multiple_baskets(self):
        """Test that ordering succeeds if multiple editable baskets exist for the user."""
        User = get_user_model()
        user = User.objects.create_user(
            username=self.USER_DATA['username'],
        )

        # Create two editable baskets for the user
        for _ in xrange(2):
            basket = Basket(owner=user, status='Open')
            basket.save()

        # Verify that a new order can be created successfully
        self._create_and_verify_order(self.EXPENSIVE_TRIAL_SKU, self.SHIPPING_EVENT_NAME)

    @raises(errors.ShippingEventNotFoundError)
    def test_create_bad_shipping_event(self):
        """Test that attempts to create a non-existent shipping event fail."""
        data.get_shipping_event_type(self.NONEXISTENT_SHIPPING_EVENT_NAME)

    @mock.patch('oscar.apps.partner.strategy.Structured.fetch_for_product')
    def test_order_unavailable_product(self, mock_fetch_for_product):
        """Test that orders for unavailable products fail with appropriate messaging."""
        OrderInfo = namedtuple('OrderInfo', 'availability')
        Availability = namedtuple('Availability', ['is_available_to_buy', 'message'])

        order_info = OrderInfo(Availability(self.UNAVAILABLE, self.UNAVAILABLE_MESSAGE))
        mock_fetch_for_product.return_value = order_info

        response = self._order(sku=self.EXPENSIVE_TRIAL_SKU)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data,
            self._bad_request_dict(
                self.UNAVAILABLE_MESSAGE,
                errors.PRODUCT_UNAVAILABLE_USER_MESSAGE
            )
        )

    def test_missing_sku(self):
        """Test that requests made to the orders endpoint without a SKU fail with appropriate messaging."""
        response = self._order()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data,
            self._bad_request_dict(
                errors.SKU_NOT_FOUND_DEVELOPER_MESSAGE,
                errors.SKU_NOT_FOUND_USER_MESSAGE
            )
        )

    def test_no_product_for_sku(self):
        """Test that orders for non-existent products fail with appropriate messaging."""
        response = self._order(sku=self.FREE_TRIAL_SKU)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data,
            self._bad_request_dict(
                errors.PRODUCT_NOT_FOUND_DEVELOPER_MESSAGE.format(sku=self.FREE_TRIAL_SKU),
                errors.PRODUCT_NOT_FOUND_USER_MESSAGE
            )
        )

    def test_throttling(self):
        """Test that the rate of requests to the orders endpoint is throttled."""
        request_limit = OrdersThrottle().num_requests
        # Make a number of requests equal to the number of allowed requests
        for _ in xrange(request_limit):
            self._order(sku=self.EXPENSIVE_TRIAL_SKU)

        # Make one more request to trigger throttling of the client
        response = self._order(sku=self.EXPENSIVE_TRIAL_SKU)
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn("Request was throttled.", response.data['detail'])

    def test_jwt_authentication(self):
        """Test that requests made to the orders endpoint without a valid JWT fail."""
        # Verify that the orders endpoint requires JWT authentication
        response = self._order(sku=self.EXPENSIVE_TRIAL_SKU, auth=False)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Verify that the orders endpoint requires valid user data in the JWT payload
        token = self._generate_token({})
        response = self._order(self.EXPENSIVE_TRIAL_SKU, token=token)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Verify that the orders endpoint requires user data to be signed with a valid secret;
        # guarantee an invalid secret by truncating the valid secret
        invalid_secret = self.JWT_SECRET_KEY[:-1]
        token = self._generate_token(self.USER_DATA, secret=invalid_secret)
        response = self._order(self.EXPENSIVE_TRIAL_SKU, token=token)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def _generate_token(self, payload, secret=None):
        secret = secret or self.JWT_SECRET_KEY
        token = jwt.encode(payload, secret)
        return token

    def _order(self, sku=None, auth=True, token=None):
        order_data = {}
        if sku:
            order_data['sku'] = sku

        if auth:
            token = token or self._generate_token(self.USER_DATA)
            response = self.client.post(reverse('orders:create_list'), order_data, HTTP_AUTHORIZATION='JWT ' + token)
        else:
            response = self.client.post(reverse('orders:create_list'), order_data)

        return response

    def _create_and_verify_order(self, sku, shipping_event_name):
        # Ideally, we'd use Oscar's ShippingEventTypeFactory here, but it's not exposed/public.
        ShippingEventType.objects.create(code='shipped', name=shipping_event_name)

        response = self._order(sku=sku)

        # Verify that the orders endpoint has successfully created the order
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify that the order data in the response is valid
        response_serializer = OrderSerializer(data=response.data)
        self.assertTrue(response_serializer.is_valid(), msg=response_serializer.errors)

        # Verify that the returned order metadata lines up with the order in the system
        expected_serializer = OrderSerializer(Order.objects.get())
        self.assertEqual(response_serializer.data, expected_serializer.data)

    def _bad_request_dict(self, developer_message, user_message):
        bad_request_dict = {
            'developer_message': developer_message,
            'user_message': user_message
        }
        return bad_request_dict


@ddt.ddt
class FulfillOrderViewTests(UserMixin, TestCase):
    def setUp(self):
        super(FulfillOrderViewTests, self).setUp()
        ShippingEventType.objects.create(code='shipped', name=FulfillmentMixin.SHIPPING_EVENT_NAME)

        self.user = self.create_user(is_superuser=True)
        self.client.login(username=self.user.username, password=self.password)

        self.order = factories.create_order()
        self.order.status = ORDER.FULFILLMENT_ERROR
        self.order.save()
        self.order.lines.all().update(status=LINE.FULFILLMENT_CONFIGURATION_ERROR)

        self.url = reverse('orders:fulfill', kwargs={'number': self.order.number})

    def _put_to_view(self):
        """
        PUT to the view being tested.

        Returns
            Response
        """
        return self.client.put(self.url)

    @ddt.data('delete', 'get', 'post')
    def test_post_required(self, method):
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

    @ddt.data(ORDER.OPEN, ORDER.ORDER_CANCELLED, ORDER.BEING_PROCESSED, ORDER.PAYMENT_CANCELLED, ORDER.PAID,
              ORDER.COMPLETE, ORDER.REFUNDED)
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


class ListOrderViewTests(AccessTokenMixin, ThrottlingMixin, UserMixin, TestCase):
    def setUp(self):
        super(ListOrderViewTests, self).setUp()
        self.path = reverse('orders:create_list')
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
