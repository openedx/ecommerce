

import json
from datetime import datetime
from decimal import Decimal

import ddt
import httpretty
import mock
import pytz
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import RequestFactory, override_settings
from django.urls import reverse
from oscar.core.loading import get_class, get_model
from oscar.test import factories
from rest_framework import status

from ecommerce.coupons.tests.mixins import DiscoveryMockMixin
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.entitlements.utils import create_or_update_course_entitlement
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
        self.assertEqual(content['results'][0]['number'], str(order.number))

        # Test ordering
        order_2 = create_order(site=self.site, user=self.user)
        response = self.client.get(self.path, HTTP_AUTHORIZATION=self.token)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content.decode('utf-8'))

        self.assertEqual(content['count'], 2)
        self.assertEqual(content['results'][0]['number'], str(order_2.number))
        self.assertEqual(content['results'][1]['number'], str(order.number))

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
        self.assertEqual(content['results'][0]['number'], str(order.number))

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
        self.assertEqual(content['results'][0]['number'], str(order.number))

    def test_user_information(self):
        """ Make sure that the correct user information is returned. """
        admin_user = self.create_user(is_staff=True, is_superuser=True)
        order = create_order(site=self.site, user=admin_user)

        response = self.client.get(self.path, HTTP_AUTHORIZATION=self.generate_jwt_token_header(admin_user))
        content = json.loads(response.content.decode('utf-8'))
        self.assertEqual(content['count'], 1)
        self.assertEqual(content['results'][0]['number'], str(order.number))
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
        self.assertEqual(content['results'][0]['number'], str(second_order.number))
        self.assertEqual(content['results'][1]['number'], str(order.number))

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
        self.assertEqual(content['results'][0]['number'], str(second_order.number))
        self.assertEqual(content['results'][1]['number'], str(order.number))


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
        self.assertEqual(str(self.order.number), response.data['number'])
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
        with mock.patch.object(post_checkout, 'send', side_effect=post_checkout.send):
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
        with mock.patch.object(post_checkout, 'send', side_effect=post_checkout.send):
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


@ddt.ddt
@httpretty.activate
class ManualCourseEnrollmentOrderViewSetTests(TestCase, DiscoveryMockMixin):
    """
    Test the `ManualCourseEnrollmentOrderViewSet` functionality.
    """
    def setUp(self):
        super(ManualCourseEnrollmentOrderViewSetTests, self).setUp()
        self.url = reverse('api:v2:manual-course-enrollment-order-list')
        self.user = self.create_user(is_staff=True)
        self.client.login(username=self.user.username, password=self.password)
        self.course = CourseFactory(id='course-v1:MAX+CX+Course', partner=self.partner)
        self.course_uuid = '620a5ce5-6ff4-4b2b-bea1-a273c6920ae5'
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
        self.course_entitlement = create_or_update_course_entitlement(
            'verified', 100, self.partner, self.course_uuid, 'Course Entitlement'
        )
        self.mock_access_token_response()
        self.mock_course_run_detail_endpoint(
            self.course,
            discovery_api_url=self.site.siteconfiguration.discovery_api_url,
            course_run_info={
                'course_uuid': self.course_uuid
            }
        )

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

        error_detail = "Missing required enrollment data: 'lms_user_id', 'username', 'email', 'course_run_key', 'mode'"
        self.assertEqual(response_data, {
            "orders": [{
                "status": "failure",
                "detail": error_detail,
                "new_order_created": None
            }]
        })

    @ddt.unpack
    @ddt.data(
        (0.0, True),
        (50.0, True),
        (100.0, True),
        (-1.0, False),
        (100.001, False),
        (50, False),
    )
    def test_create_manual_order_with_discount_percentage(self, discount_percentage, is_valid):
        """"
        Test that orders with valid and invalid discount percentages.
        """

        post_data = self.generate_post_data(1, discount_percentage=discount_percentage)
        _, response_data = self.post_order(post_data, self.user)
        if is_valid:
            self.assertEqual(len(response_data.get("orders")), 1)
            self.assertEqual(response_data.get('orders')[0]['status'], "success")
        else:
            self.assertEqual(response_data.get('orders')[0]['status'], "failure")
            self.assertEqual(
                response_data.get('orders')[0]['detail'],
                "Discount percentage should be a float from 0 to 100."
            )

    @ddt.unpack
    @ddt.data(
        ("verified", True),
        ("honor", False),
        ("audit", False),
    )
    def test_create_manual_order_with_mode(self, course_mode, is_paid):
        """"
        Test that orders with valid and invalid course modes.
        """
        post_data = self.generate_post_data(1, mode=course_mode)
        _, response_data = self.post_order(post_data, self.user)
        if is_paid:
            self.assertEqual(len(response_data.get("orders")), 1)
            self.assertEqual(response_data.get('orders')[0]['status'], "success")
        else:
            self.assertEqual(response_data.get('orders')[0]['status'], "failure")
            self.assertEqual(
                response_data.get('orders')[0]['detail'],
                "Course mode should be paid"
            )

    def test_create_manual_order(self):
        """"
        Test that manual enrollment order can be created with expected data.
        """
        post_data = {
            "enrollments": [
                {
                    "lms_user_id": 11,
                    "username": "ma",
                    "email": "ma@example.com",
                    "course_run_key": self.course.id,
                    "mode": "verified",
                    "discount_percentage": 50.0,
                    "sales_force_id": "dummy-sales_force_id",
                },
                {
                    "lms_user_id": 12,
                    "username": "ma2",
                    "email": "ma2@example.com",
                    "discount_percentage": 0.0,
                    "sales_force_id": "",
                    "course_run_key": self.course.id,
                    "mode": "verified",
                    "enterprise_customer_name": "an-enterprise-customer",
                    "enterprise_customer_uuid": "394a5ce5-6ff4-4b2b-bea1-a273c6920ae1",
                },
                {
                    "lms_user_id": 13,
                    "username": "ma3",
                    "email": "ma3@example.com",
                    "course_run_key": self.course.id,
                    "mode": "verified",
                    "discount_percentage": 100.0,
                    "sales_force_id": None,
                    "enterprise_customer_name": "an-enterprise-customer",
                    "enterprise_customer_uuid": "394a5ce5-6ff4-4b2b-bea1-a273c6920ae1",
                },
                {
                    "lms_user_id": 14,
                    "username": "ma4",
                    "email": "ma4@example.com",
                    "course_run_key": self.course.id,
                    "mode": "verified",
                    "discount_percentage": 100.0,
                    "enterprise_customer_name": "another-enterprise-customer",
                    "enterprise_customer_uuid": "394a5ce5-6ff4-4b2b-bea1-a273c6920ae2",
                },
                # to test if enterprise_customer_name updated for existing condition
                {
                    "lms_user_id": 15,
                    "username": "ma5",
                    "email": "ma5@example.com",
                    "course_run_key": self.course.id,
                    "mode": "verified",
                    "discount_percentage": 100.0,
                    "enterprise_customer_name": "another-enterprise-customer_with_new_name",
                    "enterprise_customer_uuid": "394a5ce5-6ff4-4b2b-bea1-a273c6920ae2",
                },
                # If discount percentage is not set then effective_contract_discount_percentage should be NULL.
                {
                    "lms_user_id": 16,
                    "username": "ma6",
                    "email": "ma6@example.com",
                    "course_run_key": self.course.id,
                    "mode": "verified",
                    "enterprise_customer_name": "another-enterprise-customer_with_new_name",
                    "enterprise_customer_uuid": "394a5ce5-6ff4-4b2b-bea1-a273c6920ae2",
                }
            ]
        }

        response_status, response_data = self.post_order(post_data, self.user)

        expected_enrollments = post_data["enrollments"]
        # updating customer name to latest one
        expected_enrollments[3]['enterprise_customer_name'] = "another-enterprise-customer_with_new_name"

        self.assertEqual(response_status, status.HTTP_200_OK)

        orders = response_data.get("orders")
        self.assertEqual(len(orders), len(expected_enrollments))
        for response_order, expected_enrollment in zip(orders, expected_enrollments):
            user = User.objects.get(
                username=expected_enrollment['username'],
                email=expected_enrollment['email'],
                lms_user_id=expected_enrollment['lms_user_id']
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

            # verify line has the correct 'effective_contract_discount_percentage' and
            # line_effective_contract_discounted_price values
            discount_percentage = expected_enrollment.get('discount_percentage')
            sales_force_id = expected_enrollment.get('sales_force_id')
            if discount_percentage is None:
                self.assertEqual(line.effective_contract_discount_percentage, None)
                self.assertEqual(line.effective_contract_discounted_price, None)
            else:
                line_effective_discount_percentage = Decimal('0.01') * Decimal(discount_percentage)
                line_effective_contract_discounted_price = line.unit_price_excl_tax \
                    * (Decimal('1.00000') - line_effective_discount_percentage).quantize(Decimal('.00001'))
                self.assertEqual(line.effective_contract_discount_percentage, line_effective_discount_percentage)
                self.assertEqual(line.effective_contract_discounted_price, line_effective_contract_discounted_price)

            self.assertEqual(line.status, LINE.COMPLETE)
            self.assertEqual(line.line_price_before_discounts_incl_tax, self.course_price)
            product = Product.objects.get(id=line.product.id)
            self.assertEqual(product.course_id, self.course.id)

            # verify condition
            offer = order.discounts.first().offer
            condition = offer.condition
            if sales_force_id:
                self.assertEqual(offer.sales_force_id, sales_force_id)
            self.assertEqual(condition.enterprise_customer_name, expected_enrollment.get('enterprise_customer_name'))
            self.assertEqual(
                str(condition.enterprise_customer_uuid),
                str(expected_enrollment.get('enterprise_customer_uuid'))
            )

    def test_create_manual_order_with_date_placed(self):
        """"
        Test that manual enrollment order for old enrollment can be created correctly.
        """
        price_1 = 100
        price_2 = 200
        final_price = 300
        stock_record = self.course.seat_products.filter(
            attributes__name='certificate_type'
        ).exclude(
            attribute_values__value_text='audit'
        ).first().stockrecords.first()

        time_at_initial_price = datetime.now(pytz.utc).isoformat()

        stock_record.price_excl_tax = price_1
        stock_record.save()
        stock_record.price_excl_tax = price_2
        stock_record.save()

        time_at_price_2 = datetime.now(pytz.utc).isoformat()

        stock_record.price_excl_tax = final_price
        stock_record.save()

        time_at_final_price = datetime.now(pytz.utc).isoformat()

        self.assertEqual(stock_record.history.count(), 4)

        post_data = {
            "enrollments": [
                {
                    "lms_user_id": 11,
                    "username": "ma1",
                    "email": "ma`@example.com",
                    "date_placed": time_at_initial_price,
                    "course_run_key": self.course.id,
                    "mode": "verified",
                    "enterprise_customer_name": "an-enterprise-customer",
                    "enterprise_customer_uuid": "394a5ce5-6ff4-4b2b-bea1-a273c6920ae1",
                },
                {
                    "lms_user_id": 12,
                    "username": "ma2",
                    "email": "ma2@example.com",
                    "date_placed": time_at_price_2,
                    "course_run_key": self.course.id,
                    "mode": "verified",
                    "enterprise_customer_name": "an-enterprise-customer",
                    "enterprise_customer_uuid": "394a5ce5-6ff4-4b2b-bea1-a273c6920ae1",
                },
                {
                    "lms_user_id": 13,
                    "username": "ma3",
                    "email": "ma3@example.com",
                    "date_placed": time_at_final_price,
                    "course_run_key": self.course.id,
                    "mode": "verified",
                    "enterprise_customer_name": "an-enterprise-customer",
                    "enterprise_customer_uuid": "394a5ce5-6ff4-4b2b-bea1-a273c6920ae1",
                },
            ]
        }

        response_status, response_data = self.post_order(post_data, self.user)
        expected_enrollments = post_data["enrollments"]
        self.assertEqual(response_status, status.HTTP_200_OK)
        orders = response_data.get("orders")
        self.assertEqual(len(orders), len(expected_enrollments))

        for response_order, expected_enrollment in zip(orders, expected_enrollments):
            # get created order
            order = Order.objects.get(number=response_order['detail'])
            expected_date_placed = expected_enrollment['date_placed']
            self.assertEqual(order.date_placed.isoformat(), expected_date_placed)
            self.assertEqual(order.lines.count(), 1)
            line = order.lines.first()

            if expected_date_placed == time_at_initial_price:
                expected_course_price = self.course_price
            elif expected_date_placed == time_at_price_2:
                expected_course_price = price_2
            elif expected_date_placed == time_at_final_price:
                expected_course_price = final_price
            else:
                expected_course_price = "Invalid Price"
            self.assertEqual(line.line_price_before_discounts_incl_tax, expected_course_price)
            self.assertEqual(line.line_price_before_discounts_excl_tax, expected_course_price)
            self.assertEqual(line.line_price_incl_tax, 0)
            self.assertEqual(line.line_price_excl_tax, 0)

    def test_create_manual_order_with_existing_entitlement(self):
        """"
        Test when user had already purchased the course entitlement.
        """
        # purchasing self.course's course_entitlement for self.user
        basket = factories.BasketFactory(owner=self.user, site=self.site)
        basket.add_product(self.course_entitlement, 1)
        order = create_order(basket=basket, user=self.user)
        order.lines.update(status=LINE.COMPLETE)

        course_without_discovery_data = CourseFactory(id='course-v1:Demo+Demox+Course', partner=self.partner)

        pre_request_order_count = Order.objects.count()

        post_data = {
            "enrollments": [
                # test when user have existing course entitlement purchased.
                {
                    "lms_user_id": self.user.lms_user_id,
                    "username": self.user.username,
                    "email": self.user.email,
                    "course_run_key": self.course.id,
                    "mode": "verified",
                    "enterprise_customer_name": "an-enterprise-customer",
                    "enterprise_customer_uuid": "394a5ce5-6ff4-4b2b-bea1-a273c6920ae1",
                },
                # test when user have NOT purchased course entitlement.
                {
                    "lms_user_id": 12,
                    "username": "ma2",
                    "email": "ma2@example.com",
                    "course_run_key": self.course.id,
                    "mode": "verified",
                    "enterprise_customer_name": "an-enterprise-customer",
                    "enterprise_customer_uuid": "394a5ce5-6ff4-4b2b-bea1-a273c6920ae1",
                },
                # test if there is not any record against a course in the discovery.
                {
                    "lms_user_id": 13,
                    "username": "ma3",
                    "email": "ma3@example.com",
                    "course_run_key": course_without_discovery_data.id,
                    "mode": "verified",
                    "enterprise_customer_name": "an-enterprise-customer",
                    "enterprise_customer_uuid": "394a5ce5-6ff4-4b2b-bea1-a273c6920ae1",
                }
            ]
        }

        response_status, response_data = self.post_order(post_data, self.user)
        expected_enrollments = post_data["enrollments"]
        self.assertEqual(response_status, status.HTTP_200_OK)
        self.assertEqual(pre_request_order_count + 1, Order.objects.count())
        orders = response_data.get("orders")
        self.assertEqual(len(orders), len(expected_enrollments))

        self.assertEqual(orders[0]['status'], 'success')
        self.assertEqual(orders[0]['lms_user_id'], self.user.lms_user_id)
        self.assertEqual(orders[0]['new_order_created'], False)

        self.assertEqual(orders[1]['status'], 'success')
        self.assertEqual(orders[1]['lms_user_id'], 12)
        self.assertEqual(orders[1]['new_order_created'], True)

        self.assertEqual(orders[2]['status'], 'failure')
        self.assertEqual(orders[2]['detail'], 'Failed to create free order')

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
                dict(enrollment, status="success", detail=order_number, new_order_created=True),
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
                dict(enrollment, status="failure", detail="Course not found", new_order_created=None),
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
                    dict(enrollment, status="failure", detail="Course not found", new_order_created=None),
                    response_data["orders"][index]
                )
            else:
                # Order should succeed
                order_number = response_data["orders"][index]["detail"]
                self.assertEqual(
                    dict(enrollment, status="success", detail=order_number, new_order_created=True),
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

    def generate_post_data(self, enrollment_count, discount_percentage=0.0, mode="verified"):
        return {
            "enrollments": [
                {
                    "lms_user_id": 10 + count,
                    "username": "ma{}".format(count),
                    "email": "ma{}@example.com".format(count),
                    "course_run_key": self.course.id,
                    "mode": mode,
                    "discount_percentage": discount_percentage,
                    "enterprise_customer_name": "customer_name",
                    "enterprise_customer_uuid": "394a5ce5-6ff4-4b2b-bea1-a273c6920ae1",
                }
                for count in range(enrollment_count)
            ]
        }
