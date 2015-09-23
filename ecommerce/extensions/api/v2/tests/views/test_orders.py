import json

import ddt
from django.contrib.auth.models import Permission
from django.core.urlresolvers import reverse
from django.test import TestCase, override_settings
import httpretty
import mock
from oscar.core.loading import get_model
from oscar.test import factories

from ecommerce.extensions.api.tests.test_authentication import AccessTokenMixin, OAUTH2_PROVIDER_URL
from ecommerce.extensions.api.v2.tests.views import OrderDetailViewTestMixin
from ecommerce.extensions.fulfillment.signals import SHIPPING_EVENT_NAME
from ecommerce.extensions.fulfillment.status import ORDER
from ecommerce.tests.mixins import UserMixin, ThrottlingMixin

Order = get_model('order', 'Order')
ShippingEventType = get_model('order', 'ShippingEventType')


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
        ShippingEventType.objects.get_or_create(name=SHIPPING_EVENT_NAME)

        self.user = self.create_user(is_superuser=True)
        self.client.login(username=self.user.username, password=self.password)

        self.order = factories.create_order(user=self.user)
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

    def test_order_complete_state_disallowed(self):
        """ If the order is Complete, the view must return an HTTP 406. """
        self.order.status = ORDER.COMPLETE
        self.order.save()
        self.assertEqual(406, self._put_to_view().status_code)

    @ddt.data(ORDER.OPEN, ORDER.FULFILLMENT_ERROR)
    def test_ideal_conditions(self, order_status):
        """
        If the user is authenticated/authorized, and the order is in the Open or Fulfillment Error
        states, the view should attempt to fulfill the order. The view should return HTTP 200.
        """
        self.order.status = order_status
        self.order.save()

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
        self.order.status = ORDER.FULFILLMENT_ERROR
        self.order.save()

        response = self._put_to_view()
        self.assertEqual(500, response.status_code)


class OrderDetailViewTests(OrderDetailViewTestMixin, TestCase):
    @property
    def url(self):
        return reverse('api:v2:orders:retrieve', kwargs={'number': self.order.number})
