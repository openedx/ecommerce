"""Tests of ecommerce sailthru signal handlers."""
import logging

from mock import patch
from oscar.test.factories import create_order
from oscar.test.newfactories import UserFactory, BasketFactory
from django.test.client import RequestFactory

from ecommerce.tests.testcases import TestCase
from ecommerce.core.tests import toggle_switch
from ecommerce.sailthru.signals import process_checkout_complete, process_basket_addition
from ecommerce.courses.models import Course
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin

log = logging.getLogger(__name__)

TEST_EMAIL = "test@edx.org"


class SailthruTests(CourseCatalogTestMixin, TestCase):
    """
    Tests for the Sailthru signals class.
    """

    def setUp(self):
        super(SailthruTests, self).setUp()
        self.request_factory = RequestFactory()
        self.request = self.request_factory.get("foo")
        self.request.COOKIES['sailthru_bid'] = 'cookie_bid'
        self.request.site = self.site
        self.user = UserFactory.create(username='test', email=TEST_EMAIL)

        toggle_switch('sailthru_enable', True)

        # create some test course objects
        self.course_id = 'edX/toy/2012_Fall'
        self.course_url = 'http://lms.testserver.fake/courses/edX/toy/2012_Fall/info'
        self.course = Course.objects.create(id=self.course_id, name='Demo Course')

    @patch('ecommerce.sailthru.signals.logger.error')
    def test_just_return_signals(self, mock_log_error):
        """
        Ensure that disabling Sailthru just returns
        """
        toggle_switch('sailthru_enable', False)
        process_checkout_complete(None)
        self.assertFalse(mock_log_error.called)

        process_basket_addition(None)
        self.assertFalse(mock_log_error.called)

    @patch('ecommerce_worker.sailthru.v1.tasks.update_course_enrollment.delay')
    def test_process_checkout_complete(self, mock_update_course_enrollment):
        """
        Test that the process_checkout signal handler properly calls the task routine
        """

        seat, order = self._create_order(99)
        process_checkout_complete(None, order=order, request=self.request)
        self.assertTrue(mock_update_course_enrollment.called)
        mock_update_course_enrollment.assert_called_with(TEST_EMAIL,
                                                         self.course_url,
                                                         False,
                                                         seat.attr.certificate_type,
                                                         course_id=self.course_id,
                                                         currency=order.currency,
                                                         message_id='cookie_bid',
                                                         site_code='edX',
                                                         unit_cost=order.total_excl_tax)

    @patch('ecommerce_worker.sailthru.v1.tasks.update_course_enrollment.delay')
    def test_process_checkout_complete_no_request(self, mock_update_course_enrollment):
        """
        Test that the process_checkout signal handler properly handles null request
        """

        seat, order = self._create_order(99)
        process_checkout_complete(None, order=order)
        self.assertTrue(mock_update_course_enrollment.called)
        mock_update_course_enrollment.assert_called_with(TEST_EMAIL,
                                                         self.course_url,
                                                         False,
                                                         seat.attr.certificate_type,
                                                         course_id=self.course_id,
                                                         currency=order.currency,
                                                         message_id=None,
                                                         site_code='edX',
                                                         unit_cost=order.total_excl_tax)

    @patch('ecommerce_worker.sailthru.v1.tasks.update_course_enrollment.delay')
    def test_process_basket_addition(self, mock_update_course_enrollment):
        """
        Test that the process_basket_addition signal handler properly calls the task routine
        """

        seat, order = self._create_order(99)
        process_basket_addition(None, request=self.request,
                                user=self.user,
                                product=seat)
        self.assertTrue(mock_update_course_enrollment.called)
        mock_update_course_enrollment.assert_called_with(TEST_EMAIL,
                                                         self.course_url,
                                                         True,
                                                         seat.attr.certificate_type,
                                                         course_id=self.course_id,
                                                         currency=order.currency,
                                                         message_id='cookie_bid',
                                                         site_code='edX',
                                                         unit_cost=order.total_excl_tax)

    @patch('ecommerce_worker.sailthru.v1.tasks.update_course_enrollment.delay')
    def test_price_zero(self, mock_update_course_enrollment):
        """
        Test that a price of zero skips update_course_enrollment in process basket
        """

        seat = self._create_order(0)[0]
        process_basket_addition(None, request=self.request,
                                user=self.user,
                                product=seat)
        self.assertFalse(mock_update_course_enrollment.called)

    def _create_order(self, price):
        seat = self.course.create_or_update_seat('verified', False, price, self.partner, None)

        basket = BasketFactory()
        basket.add_product(seat, 1)
        order = create_order(number=1, basket=basket, user=self.user)
        order.total_excl_tax = price
        return seat, order
