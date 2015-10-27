"""
Tests for the checkout page.
"""
import datetime
import json

import ddt
import httpretty
import mock
from requests.exceptions import ConnectionError, Timeout

from django.conf import settings
from django.core.urlresolvers import reverse
from django.utils import timezone
from django.test import TestCase

from ecommerce.core.tests import toggle_switch
from ecommerce.courses.models import Course
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.extensions.payment.helpers import get_processor_class
from ecommerce.tests.mixins import UserMixin, PartnerMixin


JSON = 'application/json'


@ddt.ddt
class CheckoutPageTest(UserMixin, CourseCatalogTestMixin, PartnerMixin, TestCase):
    """Test for Checkout page"""

    @mock.patch('ecommerce.extensions.fulfillment.modules.parse_tracking_context', mock.Mock(return_value=(None, None)))
    def setUp(self):
        super(CheckoutPageTest, self).setUp()
        self.switch = toggle_switch('ENABLE_CREDIT_APP', True)
        self.partner = self.create_partner('edx')

        user = self.create_user(is_superuser=False)
        self.client.login(username=user.username, password=self.password)
        self.course_name = 'credit course'
        self.provider = 'ASU'
        self.price = 100
        self.thumbnail_url = 'http://www.edx.org/course.jpg'
        self.credit_hours = 2
        # Create the course
        self.course = Course.objects.create(
            id=u'edx/Demo_Course/DemoX',
            name=self.course_name,
            thumbnail_url=self.thumbnail_url
        )

        # Create the credit seat
        self.seat = self.course.create_or_update_seat(
            'credit', True, self.price, self.partner, self.provider, credit_hours=self.credit_hours
        )

    @property
    def path(self):
        return reverse('credit:checkout', args=[self.course.id])

    def get_future_date(self):
        return str(timezone.now() + datetime.timedelta(days=10))

    def get_past_date(self):
        return str(timezone.now() + datetime.timedelta(days=-10))

    @httpretty.activate
    def test_get_with_enabled_flag(self):
        """
        Test checkout page accessibility. Page will appear only if feature
        flag is enabled.
        """
        body = json.dumps([{"course_key": unicode(self.course.id), "deadline": self.get_future_date()}])
        httpretty.register_uri(httpretty.GET, settings.CREDIT_API_URL, status=200, content_type=JSON, body=body)
        response = self.client.get(self.path)

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "You are not eligible to buy this course.")
        self.assertNotContains(response, "Something went wrong. Please try again later.")

    def test_get_with_disabled_flag(self):
        """
        Test checkout page accessibility. Page will return 404 if no flag is defined
        of it is disabled.
        """
        self.switch.active = False
        self.switch.save()
        response = self.client.get(self.path)

        self.assertEqual(response.status_code, 404)

    @httpretty.activate
    def test_get_with_no_eligibility(self):
        """
        Test checkout page accessibility. Page will show an error message if user is not eligible for the
        given course.
        """
        httpretty.register_uri(httpretty.GET, settings.CREDIT_API_URL, status=200, content_type=JSON, body='[]')
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "You are not eligible to buy this course.")
        self.assertNotContains(response, "Something went wrong. Please try again later.")

    @httpretty.activate
    @ddt.data(500, 404)
    def test_get_with_eligibility_api_failure(self, status):
        """
        Test checkout page for credit eligibility. If the credit eligibility
        api fails.
        """
        body = json.dumps([{"course_key": unicode(self.course.id), "deadline": self.get_past_date()}])
        httpretty.register_uri(httpretty.GET, settings.CREDIT_API_URL, status=status, content_type=JSON, body=body)
        response = self.client.get(self.path)
        self.assertContains(response, "Something went wrong. Please try again later.")
        self.assertNotContains(response, "You are not eligible to buy this course.")

    @mock.patch('requests.get', mock.Mock(side_effect=Timeout))
    def test_get_with_eligibility_api_timeout(self):
        """
        Test checkout page for credit eligibility. Page will show an error message if the credit eligibility
        api timeout.
        """
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "You are not eligible to buy this course.")
        self.assertContains(response, "Something went wrong. Please try again later.")

    @mock.patch('requests.get', mock.Mock(side_effect=ConnectionError))
    def test_get_with_eligibility_api_connection_error(self):
        """
        Test checkout page for credit eligibility. Page will show an error message if the credit eligibility
        api connection failed.
        """
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "You are not eligible to buy this course.")
        self.assertContains(response, "Something went wrong. Please try again later.")

    @httpretty.activate
    def test_get_checkout_page_with_credit_seats(self):
        """ Verify page loads and has the necessary context. """
        body = json.dumps([{"course_key": unicode(self.course.id), "deadline": self.get_future_date()}])
        # Mock the eligibility service to return valid eligibility
        httpretty.register_uri(httpretty.GET, settings.CREDIT_API_URL, status=200, content_type=JSON, body=body)
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        expected = {
            'course': self.course,
            'credit_seats': [self.seat],
        }
        self.assertDictContainsSubset(expected, response.context)

        # Verify the payment processors are returned
        self.assertEqual(sorted(response.context['payment_processors'].keys()),
                         sorted([get_processor_class(path).NAME.lower() for path in settings.PAYMENT_PROCESSORS]))

        self.assertContains(
            response,
            'Purchase {} credits from'.format(self.credit_hours)
        )
        self.assertNotContains(response, "You are not eligible to buy this course.")
        self.assertNotContains(response, "Something went wrong. Please try again later.")

    @httpretty.activate
    def test_course_not_found(self):
        """ The view should return HTTP 404 if the course cannot be found. """
        body = json.dumps([{"course_key": unicode('course/not/found'), "deadline": self.get_future_date()}])
        httpretty.register_uri(httpretty.GET, settings.CREDIT_API_URL, status=200, body=body, content_type=JSON)
        path = reverse('credit:checkout', args=['course/not/found'])
        response = self.client.get(path)
        self.assertEqual(response.status_code, 404)
