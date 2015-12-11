"""
Tests for the checkout page.
"""
from __future__ import unicode_literals
import json

from django.conf import settings
from django.core.urlresolvers import reverse
import httpretty

from ecommerce.core.tests import toggle_switch
from ecommerce.courses.models import Course
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.extensions.payment.helpers import get_processor_class
from ecommerce.settings import get_lms_url
from ecommerce.tests.mixins import JwtMixin
from ecommerce.tests.testcases import TestCase

JSON = 'application/json'


class CheckoutPageTest(CourseCatalogTestMixin, TestCase, JwtMixin):
    """Test for Checkout page"""

    def setUp(self):
        super(CheckoutPageTest, self).setUp()
        self.switch = toggle_switch('ENABLE_CREDIT_APP', True)

        user = self.create_user(is_superuser=False)
        self.create_access_token(user)
        self.client.login(username=user.username, password=self.password)
        self.course_name = 'credit course'
        self.provider = 'ASU'
        self.price = 100
        self.thumbnail_url = 'http://www.edx.org/course.jpg'
        self.credit_hours = 2
        self.eligibility_url = get_lms_url('/api/credit/v1/eligibility/')
        self.provider_url = get_lms_url('/api/credit/v1/providers/')

        # Create the course
        self.course = Course.objects.create(
            id='edx/Demo_Course/DemoX',
            name=self.course_name,
            thumbnail_url=self.thumbnail_url
        )

        self.provider_data = [
            {
                'enable_integration': False,
                'description': 'Arizona State University',
                'url': 'https://credit.example.com/',
                'status_url': 'https://credit.example.com/status',
                'thumbnail_url': 'http://edX/DemoX/asset/images_course_image.jpg',
                'fulfillment_instructions': 'Sample fulfilment requirement.',
                'display_name': 'Arizona State University',
                'id': 'ASU'
            }
        ]

        self.eligibilities = [
            {
                'deadline': '2016-10-28T09:56:44Z',
                'course_key': 'edx/cs01/2015'
            }
        ]

    @property
    def path(self):
        return reverse('credit:checkout', args=[self.course.id])

    def _mock_eligibility_api(self, body, status=200):
        """ Mock GET requests to the Credit API's eligibility endpoint. """

        httpretty.register_uri(
            method=httpretty.GET,
            uri=self.eligibility_url,
            status=status,
            content_type=JSON,
            body=json.dumps(body)
        )

    def _mock_providers_api(self, body, status=200):
        """ Mock GET requests to the Credit API's provider endpoint. """

        httpretty.register_uri(
            method=httpretty.GET,
            uri=self.provider_url,
            status=status,
            content_type=JSON,
            body=json.dumps(body)
        )

    def test_get_with_disabled_flag(self):
        """
        Test checkout page accessibility. Page will return 404 if no flag is defined
        of it is disabled.
        """
        self.switch.active = False
        self.switch.save()
        response = self.client.get(self.path)

        self.assertEqual(response.status_code, 404)

    def _assert_error_without_deadline(self):
        """ Verify that response has eligibility error message if no eligibility
        is available.
        """
        response = self.client.get(self.path)
        self.assertContains(
            response,
            u"An error has occurred. We could not confirm that you are eligible for course credit."
        )

    def _assert_error_without_providers(self):
        """ Verify that response has providers error message if no provider is
        available.
        """
        response = self.client.get(self.path)
        self.assertContains(
            response,
            u"An error has occurred. We could not confirm that the institution you selected offers "
            u"this course credit."
        )

    def _assert_success_checkout_page(self):
        """ Verify that checkout page load successfully, and has necessary context. """

        # Create the credit seat
        self.course.create_or_update_seat(
            'credit', True, self.price, self.partner, self.provider, credit_hours=self.credit_hours
        )

        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        self.assertDictContainsSubset({'course': self.course}, response.context)

        # Verify that the payment processors are returned
        self.assertEqual(
            sorted(response.context['payment_processors'].keys()),
            sorted([get_processor_class(path).NAME.lower() for path in settings.PAYMENT_PROCESSORS])
        )

        self.assertContains(
            response,
            'Congratulations! You are eligible to purchase academic course credit for this course.'
        )

    def test_course_not_found(self):
        """ The view should return HTTP 404 if the course cannot be found. """
        path = reverse('credit:checkout', args=['course/not/found'])
        response = self.client.get(path)
        self.assertEqual(response.status_code, 404)

    @httpretty.activate
    def test_get_without_deadline(self):
        """ Verify an error is shown if the user is not eligible for credit. """
        self._mock_eligibility_api(body=[])
        self._assert_error_without_deadline()

    @httpretty.activate
    def test_get_without_provider(self):
        """ Verify an error is shown if the Credit API returns an empty list of
        providers.
        """
        self._mock_eligibility_api(body=self.eligibilities)

        # Create the credit seat
        self.course.create_or_update_seat(
            'credit', True, self.price, self.partner, self.provider, credit_hours=self.credit_hours
        )
        self._mock_providers_api(body=[])
        self._assert_error_without_providers()

    @httpretty.activate
    def test_eligibility_api_failure(self):
        """ Verify an error is shown if an exception is raised when requesting
        eligibility information from the Credit API.
        """
        self._mock_eligibility_api(body=[], status=500)
        self._assert_error_without_deadline()

    @httpretty.activate
    def test_provider_api_failure(self):
        """ Verify an error is shown if an exception is raised when requesting
        provider(s) details from the Credit API.
        """

        # Create the credit seat
        self.course.create_or_update_seat(
            'credit', True, self.price, self.partner, self.provider, credit_hours=self.credit_hours
        )
        self._mock_eligibility_api(body=self.eligibilities)
        self._mock_providers_api(body=[], status=500)
        self._assert_error_without_providers()

    @httpretty.activate
    def test_get_checkout_page_with_credit_seats(self):
        """ Verify the page loads with the proper context, if all Credit API
        calls return successfully.
        """
        # Create the credit seat
        self.course.create_or_update_seat(
            'credit', True, self.price, self.partner, self.provider, credit_hours=self.credit_hours
        )

        self._mock_eligibility_api(body=self.eligibilities)
        self._mock_providers_api(body=self.provider_data)

        self._assert_success_checkout_page()

    @httpretty.activate
    def test_get_checkout_page_with_audit_seats(self):
        """ Verify the page loads with the proper context, if all Credit API
        calls return successfully.
        """
        # Create the credit seat
        self.course.create_or_update_seat(
            'credit', True, self.price, self.partner, self.provider, credit_hours=self.credit_hours
        )

        # Create the audit seat
        self.course.create_or_update_seat('', False, 0, self.partner)

        self._mock_eligibility_api(body=self.eligibilities)
        self._mock_providers_api(body=self.provider_data)

        self._assert_success_checkout_page()

    @httpretty.activate
    def test_get_without_credit_seat(self):
        """ Verify an error is shown if the Credit API returns an empty list
        of providers.
        """
        self._mock_eligibility_api(body=self.eligibilities)

        response = self.client.get(self.path)
        self.assertEqual(response.context['error'], 'No credit seat is available for this course.')
