from __future__ import absolute_import

import json

import ddt
import httpretty
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.urls import reverse
from faker import Factory as FakerFactory
from oscar.core.loading import get_model
from oscar.test import factories
from rest_framework import status
from testfixtures import LogCapture

from ecommerce.coupons.tests.mixins import DiscoveryMockMixin
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.entitlements.utils import create_or_update_course_entitlement
from ecommerce.extensions.refund.status import REFUND, REFUND_LINE
from ecommerce.extensions.test.factories import create_order
from ecommerce.tests.testcases import TestCase

Order = get_model('order', 'Order')
OrderLine = get_model('order', 'Line')
Refund = get_model('refund', 'Refund')
User = get_user_model()

FAKER = FakerFactory.create()
LOGGER_NAME = 'ecommerce.extensions.order.management.commands.create_refund_for_orders'


@httpretty.activate
@ddt.ddt
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

    @ddt.data(True, False)
    def test_create_refund_for_duplicate_orders_only(self, commit):
        """
        Test that refund is generated for manual enrollment orders only if having some duplicate enrollments.
        """

        orders = self.create_manual_order()
        filename = 'orders_file.txt'
        self.create_orders_file(orders, filename)

        # create duplicate order having course_entitlement product
        order_with_duplicate = orders[0]
        order_without_duplicate = orders[1]

        course_uuid = FAKER.uuid4()  # pylint: disable=no-member
        order = Order.objects.get(number=order_with_duplicate['detail'])
        course_entitlement = create_or_update_course_entitlement(
            'verified', 100, order.partner, course_uuid, 'Course Entitlement'
        )
        basket = factories.BasketFactory(owner=order.user, site=order.site)
        basket.add_product(course_entitlement, 1)
        create_order(basket=basket, user=order.user)
        self.mock_access_token_response()
        self.mock_course_run_detail_endpoint(
            self.course,
            discovery_api_url=order.site.siteconfiguration.discovery_api_url,
            course_run_info={
                'course_uuid': course_uuid
            }
        )

        self.assertFalse(Refund.objects.exists())
        with LogCapture(LOGGER_NAME) as log_capture:
            params = ['create_refund_for_orders', '--order-numbers-file={}'.format(filename), '--refund-duplicate-only',
                      '--sleep-time=0.5']
            if not commit:
                params.append('--no-commit')
            call_command(*params)
            log_capture.check_present(
                (LOGGER_NAME, 'INFO', 'Sleeping for 0.5 second/seconds'),
            )
            log_capture.check_present(
                (
                    LOGGER_NAME,
                    'ERROR',
                    '[Ecommerce Order Refund]: Completed refund generation. 0 of 2 failed and 1 skipped.\n'
                    'Failed orders: \n'
                    'Skipped orders: {}\n'.format(order_without_duplicate['detail']),
                ),
            )
        if commit:
            self.assertEqual(Refund.objects.count(), 1)

            refund = Refund.objects.get(order=order)
            self.assert_refund_matches_order(refund, order)
            order = Order.objects.get(number=order_without_duplicate['detail'])
            self.assertFalse(order.refunds.exists())
        else:
            self.assertEqual(Refund.objects.count(), 0)

    def test_invalid_file_path(self):
        """
        Verify command raises the CommandError for invalid file path.
        """
        with self.assertRaises(CommandError):
            call_command('create_refund_for_orders', '--order-numbers-file={}'.format("invalid/order_id/file/path"))

        with self.assertRaises(CommandError):
            call_command('create_refund_for_orders')

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
