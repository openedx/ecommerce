import datetime
import logging

from bok_choy.web_app_test import WebAppTest

from acceptance_tests.api import EnrollmentApiClient, EcommerceApiClient
from acceptance_tests.config import COURSE_ID, LMS_USERNAME, ORDER_PROCESSING_TIME
from acceptance_tests.mixins import LoginMixin


log = logging.getLogger(__name__)


class LoginEnrollmentTests(LoginMixin, WebAppTest):
    def setUp(self):
        super(LoginEnrollmentTests, self).setUp()
        self.course_id = COURSE_ID
        self.username = LMS_USERNAME
        self.enrollment_api_client = EnrollmentApiClient()
        self.ecommerce_api_client = EcommerceApiClient()

        # TODO Delete existing enrollments

    def _test_honor_enrollment_common(self):
        """
        Validates an order is created for the logged in user and that a corresponding order has been created.
        """
        # Get the latest order
        orders = self.ecommerce_api_client.orders()
        self.assertGreater(len(orders), 0, 'No orders found for the user!')
        order = orders[0]

        # TODO Find a better way to verify this is the correct enrollment.
        # Verify the date and status
        self.assertEqual(order['status'], 'Complete')

        order_date = order['date_placed']
        now = datetime.datetime.utcnow()
        self.assertLess(order_date, now)
        self.assertGreater(order_date, now - datetime.timedelta(seconds=ORDER_PROCESSING_TIME))

        # Verify user enrolled in course
        status = self.enrollment_api_client.get_enrollment_status(self.username, self.course_id)
        log.debug(status)
        self.assertDictContainsSubset({'is_active': True, 'mode': 'honor'}, status)

    def test_honor_enrollment_and_login(self):
        """ Verifies that a user can login and enroll in a course via the login page. """

        # Login and enroll via LMS
        self.login_with_lms(self.course_id)

        self._test_honor_enrollment_common()
