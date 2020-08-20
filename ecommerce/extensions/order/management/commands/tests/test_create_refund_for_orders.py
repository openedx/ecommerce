from __future__ import absolute_import

import json

import httpretty
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.urls import reverse
from oscar.core.loading import get_model
from rest_framework import status

from ecommerce.coupons.tests.mixins import DiscoveryMockMixin
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.refund.status import REFUND, REFUND_LINE
from ecommerce.tests.testcases import TestCase

Order = get_model('order', 'Order')
OrderLine = get_model('order', 'Line')
Refund = get_model('refund', 'Refund')
User = get_user_model()


@httpretty.activate
class CreateRefundForOrdersTests(DiscoveryMockMixin, TestCase):
    """
    Test the `create_refund_for_orders` command.
    """
    def setUp(self):
        super(CreateRefundForOrdersTests, self).setUp()
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
        self.mock_access_token_response()
        self.mock_course_run_detail_endpoint(
            self.course,
            discovery_api_url=self.site.siteconfiguration.discovery_api_url,
            course_run_info={
                'course_uuid': '620a5ce5-6ff4-4b2b-bea1-a273c6920ae5'
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

    def create_manual_order(self):
        """"
        Create a manual enrollment order.
        """
        discount_percentage = 50.0
        post_data = self.generate_post_data(2, discount_percentage=discount_percentage)
        response_status, response_data = self.post_order(post_data, self.user)

        self.assertEqual(response_status, status.HTTP_200_OK)

        orders = response_data.get("orders")
        self.assertEqual(len(orders), 2)

        return orders

    def generate_post_data(self, enrollment_count, discount_percentage=0.0):
        return {
            "enrollments": [
                {
                    "lms_user_id": 10 + count,
                    "username": "ma{}".format(count),
                    "mode": "verified",
                    "email": "ma{}@example.com".format(count),
                    "course_run_key": self.course.id,
                    "discount_percentage": discount_percentage
                }
                for count in range(enrollment_count)
            ]
        }

    def assert_refund_matches_order(self, refund, order):
        """ Verify the refund corresponds to the given order. """
        self.assertEqual(refund.order, order)
        self.assertEqual(refund.user, order.user)
        self.assertEqual(refund.status, REFUND.COMPLETE)
        self.assertEqual(refund.total_credit_excl_tax, order.total_excl_tax)
        self.assertEqual(refund.lines.count(), order.lines.count())

        refund_lines = refund.lines.all()
        order_lines = order.lines.all().order_by('refund_lines')
        for refund_line, order_line in zip(refund_lines, order_lines):
            self.assertEqual(refund_line.status, REFUND_LINE.COMPLETE)
            self.assertEqual(refund_line.order_line, order_line)
            self.assertEqual(refund_line.line_credit_excl_tax, order_line.line_price_excl_tax)
            self.assertEqual(refund_line.quantity, order_line.quantity)

    def create_orders_file(self, orders, filename):
        """Create a file with order numbers - one per line"""
        with open(filename, 'w') as f:
            for response_order in orders:
                order = Order.objects.get(number=response_order['detail'])
                # add to order numbers file
                f.write("%s\n" % order.number)
        f.close()

    def test_create_refund_for_orders(self):
        """
        Test that refund is generated for manual enrollment orders.
        """
        orders = self.create_manual_order()
        filename = 'orders_file.txt'
        self.create_orders_file(orders, filename)

        self.assertFalse(Refund.objects.exists())
        call_command(
            'create_refund_for_orders', '--order-numbers-file={}'.format(filename)
        )
        self.assertTrue(Refund.objects.exists())

        for response_order in orders:
            order = Order.objects.get(number=response_order['detail'])
            refund = Refund.objects.get(order=order)
            self.assert_refund_matches_order(refund, order)

    def test_invalid_file_path(self):
        """
        Verify command raises the CommandError for invalid file path.
        """
        with self.assertRaises(CommandError):
            call_command('create_refund_for_orders', '--order-numbers-file={}'.format("invalid/order_id/file/path"))

    def test_no_file_path(self):
        """
        Verify command does not change the Refund state without a file.
        """
        self.assertFalse(Refund.objects.exists())
        call_command('create_refund_for_orders')
        self.assertFalse(Refund.objects.exists())

    def test_create_refund_order_does_not_exist(self):
        """
        Test that an exception is raised when the order does not exist
        """
        orders = self.create_manual_order()
        filename = 'missing_orders_file.txt'
        self.create_orders_file(orders, filename)
        Order.objects.all().delete()
        self.assertFalse(Refund.objects.exists())
        call_command(
            'create_refund_for_orders', '--order-numbers-file={}'.format(filename)
        )
        self.assertFalse(Refund.objects.exists())

    def test_create_refund_order_line_does_not_exist(self):
        """
        Test that a RefundError is raised when the order line is missing.
        """
        orders = self.create_manual_order()
        filename = 'order_without_lines_file.txt'
        self.create_orders_file(orders, filename)
        OrderLine.objects.all().delete()
        self.assertFalse(Refund.objects.exists())
        call_command(
            'create_refund_for_orders', '--order-numbers-file={}'.format(filename)
        )
        self.assertFalse(Refund.objects.exists())
