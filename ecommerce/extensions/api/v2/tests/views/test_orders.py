from __future__ import absolute_import

import json

import ddt
import httpretty
import mock
import six
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import RequestFactory, override_settings
from django.urls import reverse
from oscar.core.loading import get_class, get_model
from rest_framework import status

from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.api.serializers import OrderSerializer
from ecommerce.extensions.api.tests.test_authentication import AccessTokenMixin
from ecommerce.extensions.api.v2.tests.views import OrderDetailViewTestMixin
from ecommerce.extensions.checkout.exceptions import BasketNotFreeError
from ecommerce.extensions.fulfillment.signals import SHIPPING_EVENT_NAME
from ecommerce.extensions.fulfillment.status import LINE, ORDER
from ecommerce.extensions.test.factories import create_order
from ecommerce.tests.factories import SiteConfigurationFactory
from ecommerce.tests.mixins import ThrottlingMixin
from ecommerce.tests.testcases import TestCase

Basket = get_model('basket', 'Basket')
Order = get_model('order', 'Order')
Product = get_model('catalogue', 'Product')
ShippingEventType = get_model('order', 'ShippingEventType')
post_checkout = get_class('checkout.signals', 'post_checkout')
User = get_user_model()


@ddt.ddt
class OrderListViewTests(AccessTokenMixin, ThrottlingMixin, TestCase):
    def setUp(self):
        super(OrderListViewTests, self).setUp()
        self.path = reverse('api:v2:order-list')
        self.user = self.create_user()
        self.token = self.generate_jwt_token_header(self.user)

    def test_not_authenticated(self):
        """ If the user is not authenticated, the view should return HTTP status 401. """
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 401)

    def assert_empty_result_response(self, response):
        """ Verifies that the view responded successfully with an empty result list. """
        self.assertEqual(response.status_code, 200)

        content = response.json()
        self.assertEqual(content['count'], 0)
        self.assertEqual(content['results'], [])

    @httpretty.activate
    def test_oauth2_authentication(self):
        """Verify clients can authenticate with OAuth 2.0."""
        auth_header = 'Bearer {}'.format(self.DEFAULT_TOKEN)

        self.mock_user_info_response(username=self.user.username)
        response = self.client.get(self.path, HTTP_AUTHORIZATION=auth_header)
        self.assert_empty_result_response(response)

    def test_no_orders(self):
        """ If the user has no orders, the view should return an empty list. """
        self.assertFalse(self.user.orders.exists())
        response = self.client.get(self.path, HTTP_AUTHORIZATION=self.token)
        self.assert_empty_result_response(response)

    def test_with_orders(self):
        """
        The view should return a list of the user's orders, sorted reverse chronologically,
        filtered by current site's partner.
        """
        order = create_order(site=self.site, user=self.user)
        site = SiteConfigurationFactory().site
        create_order(site=site, user=self.user)
        response = self.client.get(self.path, HTTP_AUTHORIZATION=self.token)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content.decode('utf-8'))

        self.assertEqual(Order.objects.count(), 2)
        self.assertEqual(content['count'], 1)
        self.assertEqual(content['results'][0]['number'], six.text_type(order.number))

        # Test ordering
        order_2 = create_order(site=self.site, user=self.user)
        response = self.client.get(self.path, HTTP_AUTHORIZATION=self.token)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content.decode('utf-8'))

        self.assertEqual(content['count'], 2)
        self.assertEqual(content['results'][0]['number'], six.text_type(order_2.number))
        self.assertEqual(content['results'][1]['number'], six.text_type(order.number))

    def test_with_other_users_orders(self):
        """ The view should only return orders for the authenticated users. """
        other_user = self.create_user()
        create_order(site=self.site, user=other_user)
        response = self.client.get(self.path, HTTP_AUTHORIZATION=self.token)
        self.assert_empty_result_response(response)

        order = create_order(site=self.site, user=self.user)
        response = self.client.get(self.path, HTTP_AUTHORIZATION=self.token)
        content = json.loads(response.content.decode('utf-8'))
        self.assertEqual(content['count'], 1)
        self.assertEqual(content['results'][0]['number'], six.text_type(order.number))

    @ddt.unpack
    @ddt.data(
        (True, True),
        (True, False),
    )
    def test_staff_superuser(self, is_staff, is_superuser):
        """ The view should return all orders for when authenticating as a staff member or superuser. """
        admin_user = self.create_user(is_staff=is_staff, is_superuser=is_superuser)
        order = create_order(site=self.site, user=self.user)

        response = self.client.get(self.path, HTTP_AUTHORIZATION=self.generate_jwt_token_header(admin_user))
        content = json.loads(response.content.decode('utf-8'))
        self.assertEqual(content['count'], 1)
        self.assertEqual(content['results'][0]['number'], six.text_type(order.number))

    def test_user_information(self):
        """ Make sure that the correct user information is returned. """
        admin_user = self.create_user(is_staff=True, is_superuser=True)
        order = create_order(site=self.site, user=admin_user)

        response = self.client.get(self.path, HTTP_AUTHORIZATION=self.generate_jwt_token_header(admin_user))
        content = json.loads(response.content.decode('utf-8'))
        self.assertEqual(content['count'], 1)
        self.assertEqual(content['results'][0]['number'], six.text_type(order.number))
        self.assertEqual(content['results'][0]['user']['email'], admin_user.email)
        self.assertEqual(content['results'][0]['user']['username'], admin_user.username)

    def test_username_filter_with_staff(self):
        """ Verify the staff user can filter data by username."""

        # create two orders for different users
        order = create_order(site=self.site, user=self.user)
        other_user = self.create_user()
        other_order = create_order(site=self.site, user=other_user)

        requester = self.create_user(is_staff=True)
        self.client.login(email=requester.email, password=self.password)

        self.assert_list_with_username_filter(self.user, order)
        self.assert_list_with_username_filter(other_user, other_order)

    def test_username_filter_with_non_staff(self):
        """Non staff users are not allowed to filter on any other username."""
        requester = self.create_user(is_staff=False)
        self.client.login(username=requester.username, password=self.password)

        response = self.client.get(self.path, {'username': self.user.username})
        self.assertEqual(response.status_code, 403)

    def assert_list_with_username_filter(self, user, order):
        """ Helper method for making assertions. """

        response = self.client.get(self.path, {'username': user.username})
        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.data['results'][0],
            OrderSerializer(order, context={'request': RequestFactory(SERVER_NAME=self.site.domain).get('/')}).data
        )

    def test_orders_with_multiple_sites(self):
        """
        The view should return a list of the user's orders for multiple sites against same partner.
        """
        order = create_order(site=self.site, user=self.user)
        second_order = create_order(site=self.site, user=self.user)
        response = self.client.get(self.path, HTTP_AUTHORIZATION=self.token)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content.decode('utf-8'))

        self.assertEqual(Order.objects.count(), 2)
        self.assertEqual(content['count'], 2)
        self.assertEqual(content['results'][0]['number'], six.text_type(second_order.number))
        self.assertEqual(content['results'][1]['number'], six.text_type(order.number))

        # Configure new site for same partner.
        domain = 'testserver.fake.internal'
        site_configuration = SiteConfigurationFactory(
            from_email='from@example.com',
            oauth_settings={
                'SOCIAL_AUTH_EDX_OAUTH2_KEY': 'key',
                'SOCIAL_AUTH_EDX_OAUTH2_SECRET': 'secret'
            },
            partner=self.partner,
            segment_key='fake_segment_key',
            site__domain=domain,
            base_cookie_domain=domain,
        )

        self.request.site = site_configuration.site
        self.client = self.client_class(SERVER_NAME=domain)

        response = self.client.get(self.path, HTTP_AUTHORIZATION=self.token)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content.decode('utf-8'))

        self.assertEqual(content['count'], 2)
        self.assertEqual(content['results'][0]['number'], six.text_type(second_order.number))
        self.assertEqual(content['results'][1]['number'], six.text_type(order.number))


@ddt.ddt
@override_settings(ECOMMERCE_SERVICE_WORKER_USERNAME='test-service-user')
class OrderFulfillViewTests(TestCase):
    def setUp(self):
        super(OrderFulfillViewTests, self).setUp()
        ShippingEventType.objects.get_or_create(name=SHIPPING_EVENT_NAME)

        # Use the ecommerce worker service user in order to cover
        # request throttling code in extensions/api/throttles.py
        self.user = self.create_user(is_staff=True, username='test-service-user')
        self.change_order_permission = Permission.objects.get(codename='change_order')
        self.user.user_permissions.add(self.change_order_permission)

        self.client.login(username=self.user.username, password=self.password)

        self.order = create_order(site=self.site, user=self.user)
        self.url = reverse('api:v2:order-fulfill', kwargs={'number': self.order.number})

    def _put_to_view(self):
        """
        PUT to the view being tested.

        Returns:
            Response
        """
        return self.client.put(self.url)

    def _assert_fulfillment_success(self):
        """Verify that order fulfillment was successful. The view should return HTTP 200."""
        with mock.patch('ecommerce.extensions.order.processing.EventHandler.handle_shipping_event') as mocked:
            def handle_shipping_event(order, _event_type, _lines, _line_quantities, **_kwargs):
                order.status = ORDER.COMPLETE
                order.save()
                return order

            mocked.side_effect = handle_shipping_event
            response = self._put_to_view()

        self.assertTrue(mocked.called)
        self.assertEqual(200, response.status_code)

        return response

    @ddt.data('delete', 'get', 'post')
    def test_delete_get_post_prohibited(self, method):
        """Verify that the view does not allow DELETE, GET, or POST."""
        response = getattr(self.client, method)(self.url)

        # TODO: Since the view is routed to PUT and PATCH, DELETE, GET, and
        # POST *should* all be met with 405. However, permissions checks appear
        # to occur first. As a result, when a user with change permissions
        # attempts a POST or DELETE, the response has status code 403, since
        # the user doesn't have permission to create or delete orders.
        self.assertIn(response.status_code, [405, 403])

    def test_login_required(self):
        """ The view should return HTTP 401 status if the user is not logged in. """
        self.client.logout()
        self.assertEqual(401, self._put_to_view().status_code)

    def test_change_permissions_required(self):
        """
        Verify that staff users with permission to change Order objects are
        able to modify orders on behalf of other users.
        """
        customer = self.create_user(username='customer')
        customer_order = create_order(site=self.site, user=customer)
        self.url = reverse('api:v2:order-fulfill', kwargs={'number': customer_order.number})

        self._assert_fulfillment_success()

        # If the requesting user does not have the correct permissions, the view should
        # return HTTP 403 status.
        self.user.user_permissions.remove(self.change_order_permission)
        self.assertEqual(403, self._put_to_view().status_code)

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

        response = self._assert_fulfillment_success()

        # Reload the order from the DB and check its status
        self.order = Order.objects.get(number=self.order.number)
        self.assertEqual(six.text_type(self.order.number), response.data['number'])
        self.assertEqual(self.order.status, response.data['status'])

    def test_fulfillment_failed(self):
        """ If fulfillment fails, the view should return HTTP 500. """
        self.order.status = ORDER.FULFILLMENT_ERROR
        self.order.save()

        response = self._put_to_view()
        self.assertEqual(500, response.status_code)

    def test_email_opt_in_default(self):
        """
        Verify that email_opt_in defaults to false if not given.
        """
        post_checkout.send = mock.MagicMock(side_effect=post_checkout.send)
        self._assert_fulfillment_success()
        send_arguments = {
            'sender': post_checkout,
            'order': self.order,
            'request': mock.ANY,
            'email_opt_in': False,
        }
        post_checkout.send.assert_called_once_with(**send_arguments)

    @ddt.data(True, False)
    def test_email_opt_in(self, expected_opt_in):
        """
        Verify that email_opt_in is set to the query param if given.
        """
        # Add email_opt_in to url
        self.url += '?email_opt_in={expected_opt_in}'.format(expected_opt_in=expected_opt_in)
        post_checkout.send = mock.MagicMock(side_effect=post_checkout.send)
        self._assert_fulfillment_success()
        send_arguments = {
            'sender': post_checkout,
            'order': self.order,
            'request': mock.ANY,
            'email_opt_in': expected_opt_in,
        }
        post_checkout.send.assert_called_once_with(**send_arguments)


class OrderDetailViewTests(OrderDetailViewTestMixin, TestCase):
    @property
    def url(self):
        return reverse('api:v2:order-detail', kwargs={'number': self.order.number})


class ManualCourseEnrollmentOrderViewSetTests(TestCase):
    """
    Test the `ManualCourseEnrollmentOrderViewSet` functionality.
    """
    def setUp(self):
        super(ManualCourseEnrollmentOrderViewSetTests, self).setUp()
        self.url = reverse('api:v2:manual-course-enrollment-order-list')
        self.user = self.create_user(is_staff=True)
        self.client.login(username=self.user.username, password=self.password)
        self.course = CourseFactory(id='course-v1:MAX+CX+Course', partner=self.partner)
        self.course_price = 50
        self.course.create_or_update_seat(
            certificate_type='verified',
            id_verification_required=True,
            price=self.course_price
        )
        self.course.create_or_update_seat(
            certificate_type='audit',
            id_verification_required=False,
            price=0
        )
        self.post_data = {
            "enrollments": [
                {
                    "lms_user_id": 11,
                    "username": "ma",
                    "email": "ma@example.com",
                    "course_run_key": self.course.id
                },
                {
                    "lms_user_id": 12,
                    "username": "ma2",
                    "email": "ma2@example.com",
                    "course_run_key": self.course.id
                }
            ]
        }

    def build_jwt_header(self, user):
        """
        Return header for the JWT auth.
        """
        return {'HTTP_AUTHORIZATION': self.generate_jwt_token_header(user)}

    def post_order(self, data, user):
        """
        Make HTTP POST request and return the JSON response.
        """
        data = json.dumps(data)
        headers = self.build_jwt_header(user)
        response = self.client.post(self.url, data, content_type='application/json', **headers)
        return response.status_code, response.json()

    def test_auth(self):
        """
        Test that endpoint only works with the staff user
        """
        post_data = self.generate_post_data(1)
        # Test unauthenticated access
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Test non-staff user
        non_staff_user = self.create_user(is_staff=False)
        status_code, __ = self.post_order(post_data, non_staff_user)
        self.assertEqual(status_code, status.HTTP_403_FORBIDDEN)

        # Test staff user
        status_code, __ = self.post_order(post_data, self.user)
        self.assertEqual(status_code, status.HTTP_200_OK)

    def test_bad_request(self):
        """
        Test that HTTP 400 is return if `enrollments` key isn't in request
        """
        response_status, response_data = self.post_order({}, self.user)

        self.assertEqual(response_status, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response_data, {
            "status": "failure",
            "detail": "Invalid data. No `enrollments` field."
        })

    def test_missing_enrollment_data(self):
        """"
        Test that orders are marked as failures if expected data is not present in enrollment.
        """

        # Single enrollment with no enrollment details
        post_data = {"enrollments": [{}]}
        _, response_data = self.post_order(post_data, self.user)

        self.assertEqual(response_data, {
            "orders": [{
                "status": "failure",
                "detail": "Missing required enrollment data: 'lms_user_id', 'username', 'email', 'course_run_key'"
            }]
        })

    def test_create_manual_order(self):
        """"
        Test that manual enrollment order can be created with expected data.
        """
        post_data = self.generate_post_data(2)
        response_status, response_data = self.post_order(post_data, self.user)

        self.assertEqual(response_status, status.HTTP_200_OK)

        orders = response_data.get("orders")
        self.assertEqual(len(orders), 2)

        for response_order in orders:
            user = User.objects.get(
                username=response_order['username'],
                email=response_order['email'],
                lms_user_id=response_order['lms_user_id']
            )

            # get created order
            order = Order.objects.get(number=response_order['detail'])

            # verify basket owner is correct
            basket = Basket.objects.get(id=order.basket_id)

            self.assertEqual(basket.owner, user)

            # verify order is created with expected data
            self.assertEqual(order.status, ORDER.COMPLETE)
            self.assertEqual(order.total_incl_tax, 0)
            self.assertEqual(order.lines.count(), 1)
            line = order.lines.first()
            self.assertEqual(line.status, LINE.COMPLETE)
            self.assertEqual(line.line_price_before_discounts_incl_tax, self.course_price)
            product = Product.objects.get(id=line.product.id)
            self.assertEqual(product.course_id, self.course.id)

    def test_create_manual_order_with_incorrect_course(self):
        """"
        Test that manual enrollment order endpoint returns expected error response if course is incorrect.
        """
        post_data = self.generate_post_data(1)
        post_data["enrollments"][0]["course_run_key"] = "course-v1:MAX+ABC+Course"

        _, response_data = self.post_order(post_data, self.user)
        self.assertEqual(response_data["orders"][0]["detail"], "Course not found")

    def test_create_manual_order_idempotence(self):
        """"
        Test that manual enrollment order endpoint does not create multiple orders if called multiple
        times with same data.
        """
        post_data = self.generate_post_data(1)
        response_status, response_data = self.post_order(post_data, self.user)
        self.assertEqual(response_status, status.HTTP_200_OK)
        existing_order_number = response_data["orders"][0]["detail"]

        response_status, response_data = self.post_order(post_data, self.user)
        self.assertEqual(response_status, status.HTTP_200_OK)
        self.assertEqual(response_data["orders"][0]["detail"], existing_order_number)

    def test_bulk_all_correct(self):
        """
        Test that endpoint correctly handles correct bulk enrollments
        """
        post_data = self.generate_post_data(3)
        response_status, response_data = self.post_order(post_data, self.user)
        self.assertEqual(response_status, status.HTTP_200_OK)
        for index, enrollment in enumerate(post_data["enrollments"]):
            order_number = response_data["orders"][index]["detail"]
            self.assertEqual(
                dict(enrollment, status="success", detail=order_number),
                response_data["orders"][index]
            )

    def test_bulk_all_failure(self):
        """
        Test that endpoint correctly handles invalid bulk enrollments
        """
        post_data = self.generate_post_data(3)
        # Replace course run key of all enrollments with invalid course
        post_data["enrollments"] = [
            dict(enrollment, course_run_key="course-v1:MAX+ABC+Course")
            for enrollment in post_data["enrollments"]
        ]
        response_status, response_data = self.post_order(post_data, self.user)
        self.assertEqual(response_status, status.HTTP_200_OK)
        for index, enrollment in enumerate(post_data["enrollments"]):
            self.assertEqual(
                dict(enrollment, status="failure", detail="Course not found"),
                response_data["orders"][index]
            )

    def test_bulk_mixed_success(self):
        """
        Test that endpoint correctly handles a mix of correct and invalid bulk enrollments
        """
        post_data = self.generate_post_data(3)
        # Replace course run key for first enrollment only
        post_data["enrollments"][0]["course_run_key"] = "course-v1:MAX+ABC+Course"
        response_status, response_data = self.post_order(post_data, self.user)
        self.assertEqual(response_status, status.HTTP_200_OK)
        for index, enrollment in enumerate(post_data["enrollments"]):
            if index == 0:
                # Order should fail because missing enrollment
                self.assertEqual(
                    dict(enrollment, status="failure", detail="Course not found"),
                    response_data["orders"][index]
                )
            else:
                # Order should succeed
                order_number = response_data["orders"][index]["detail"]
                self.assertEqual(
                    dict(enrollment, status="success", detail=order_number),
                    response_data["orders"][index]
                )

    @mock.patch(
        'ecommerce.extensions.api.v2.views.orders.EdxOrderPlacementMixin.place_free_order',
        new_callable=mock.PropertyMock,
        side_effect=BasketNotFreeError
    )
    def test_create_manual_order_exception(self, __):
        """"
        Test that manual enrollment order endpoint returns expected error if an error occurred in
        `place_free_order`.
        """
        post_data = self.generate_post_data(1)
        _, response_data = self.post_order(post_data, self.user)
        order = response_data["orders"][0]
        self.assertEqual(order["status"], "failure")
        self.assertEqual(order["detail"], "Failed to create free order")

    def generate_post_data(self, enrollment_count):
        return {
            "enrollments": [
                {
                    "lms_user_id": 10 + count,
                    "username": "ma{}".format(count),
                    "email": "ma{}@example.com".format(count),
                    "course_run_key": self.course.id
                }
                for count in range(enrollment_count)
            ]
        }
