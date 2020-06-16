"""
Tests for the checkout page.
"""


import json
from datetime import timedelta

import ddt
import httpretty
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from oscar.core.loading import get_model
from oscar.test.factories import RangeFactory
from waffle.models import Switch

from ecommerce.core.url_utils import get_lms_url
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.extensions.payment.helpers import get_processor_class
from ecommerce.extensions.test.factories import prepare_voucher
from ecommerce.tests.mixins import JwtMixin
from ecommerce.tests.testcases import TestCase

JSON = 'application/json'
Benefit = get_model('offer', 'Benefit')


@ddt.ddt
class CheckoutPageTest(DiscoveryTestMixin, TestCase, JwtMixin):
    """Test for Checkout page"""

    def setUp(self):
        super(CheckoutPageTest, self).setUp()

        user = self.create_user(is_superuser=False)
        self.create_access_token(user)
        self.client.login(username=user.username, password=self.password)
        self.provider = 'ASU'
        self.price = 100
        self.credit_hours = 2
        self.eligibility_url = get_lms_url('/api/credit/v1/eligibility/')
        self.provider_url = get_lms_url('/api/credit/v1/providers/')
        self.course = CourseFactory(thumbnail_url='http://www.edx.org/course.jpg', partner=self.partner)

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

    def _enable_payment_providers(self):
        for path in settings.PAYMENT_PROCESSORS:
            processor = get_processor_class(path)
            Switch.objects.get_or_create(
                name=settings.PAYMENT_PROCESSOR_SWITCH_PREFIX + processor.NAME,
                defaults={'active': True}
            )

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

    def _assert_success_checkout_page(self, sku=None):
        """ Verify that checkout page load successfully, and has necessary context. """

        # Create the credit seat
        self.course.create_or_update_seat(
            'credit', True, self.price, self.provider, credit_hours=self.credit_hours, sku=sku
        )

        self._enable_payment_providers()

        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        self.assertDictContainsSubset({'course': self.course}, response.context)

        self.assertContains(
            response,
            'Congratulations! You are eligible to purchase academic course credit for this course.'
        )

        self.assertContains(
            response,
            self.provider_data[0]['fulfillment_instructions']
        )

    def test_course_not_found(self):
        """ The view should return HTTP 404 if the course cannot be found. """
        path = reverse('credit:checkout', args=['course/not/found'])
        response = self.client.get(path)
        self.assertEqual(response.status_code, 404)

    @httpretty.activate
    def test_get_without_deadline(self):
        """ Verify an error is shown if the user is not eligible for credit. """
        self.mock_access_token_response()
        self._mock_eligibility_api(body=[])
        self._assert_error_without_deadline()

    @httpretty.activate
    def test_get_without_provider(self):
        """ Verify an error is shown if the Credit API returns an empty list of
        providers.
        """
        self.mock_access_token_response()
        self._mock_eligibility_api(body=self.eligibilities)

        # Create the credit seat
        self.course.create_or_update_seat(
            'credit', True, self.price, self.provider, credit_hours=self.credit_hours
        )
        self._mock_providers_api(body=[])
        self._assert_error_without_providers()

    @httpretty.activate
    def test_eligibility_api_failure(self):
        """ Verify an error is shown if an exception is raised when requesting
        eligibility information from the Credit API.
        """
        self.mock_access_token_response()
        self._mock_eligibility_api(body=[], status=500)
        self._assert_error_without_deadline()

    @httpretty.activate
    def test_provider_api_failure(self):
        """ Verify an error is shown if an exception is raised when requesting
        provider(s) details from the Credit API.
        """

        # Create the credit seat
        self.course.create_or_update_seat(
            'credit', True, self.price, self.provider, credit_hours=self.credit_hours
        )
        self.mock_access_token_response()
        self._mock_eligibility_api(body=self.eligibilities)
        self._mock_providers_api(body=[], status=500)
        self._assert_error_without_providers()

    @httpretty.activate
    def test_get_checkout_page_with_credit_seats(self):
        """ Verify the page loads with the proper context, if all Credit API
        calls return successfully.
        """
        # Create the credit seat
        credit_seat = self.course.create_or_update_seat(
            'credit', True, self.price, self.provider, credit_hours=self.credit_hours
        )

        self.mock_access_token_response()
        self._mock_eligibility_api(body=self.eligibilities)
        self._mock_providers_api(body=self.provider_data)

        self._assert_success_checkout_page(sku=credit_seat.stockrecords.first().partner_sku)

    @httpretty.activate
    def test_get_checkout_page_with_audit_seats(self):
        """ Verify the page loads with the proper context, if all Credit API
        calls return successfully.
        """
        # Create the credit seat
        credit_seat = self.course.create_or_update_seat(
            'credit', True, self.price, self.provider, credit_hours=self.credit_hours
        )

        # Create the audit seat
        self.course.create_or_update_seat('', False, 0)

        self.mock_access_token_response()
        self._mock_eligibility_api(body=self.eligibilities)
        self._mock_providers_api(body=self.provider_data)

        self._assert_success_checkout_page(sku=credit_seat.stockrecords.first().partner_sku)

    @httpretty.activate
    def test_seat_unavailable(self):
        """ Verify the view displays an error message to the user if no seat is available for purchase. """
        expires = timezone.now() - timedelta(days=1)
        self.course.create_or_update_seat(
            'credit', True, self.price, self.provider, credit_hours=self.credit_hours, expires=expires
        )
        self.mock_access_token_response()
        self._mock_eligibility_api(body=self.eligibilities)

        response = self.client.get(self.path)
        expected = (
            'Credit is not currently available for "{course_name}". If you are currently enrolled in the '
            'course, please try again after all grading is complete. If you need additional assistance, '
            'please contact the {site_name} Support Team.'
        ).format(
            course_name=self.course.name,
            site_name=self.site.name
        )
        self.assertEqual(response.context['error'], expected)

    @httpretty.activate
    @ddt.data(
        (Benefit.PERCENTAGE, '100%'), (Benefit.FIXED, '$100.00')
    )
    @ddt.unpack
    def test_provider_fields(self, benefit_type, discount):
        code = 'TEST'
        seat = self.course.create_or_update_seat(
            'credit', True, self.price, self.provider, credit_hours=self.credit_hours
        )
        new_range = RangeFactory(products=[seat, ])
        prepare_voucher(code=code, _range=new_range, benefit_value=100, benefit_type=benefit_type)
        self.mock_access_token_response()
        self._mock_eligibility_api(body=self.eligibilities)
        self._mock_providers_api(body=self.provider_data)

        response = self.client.get('{}?code={}'.format(self.path, code))
        self.assertEqual(response.status_code, 200)
        provider_info = response.context['providers'][0]

        self.assertEqual(provider_info['new_price'], '0.00')
        self.assertEqual(provider_info['discount'], discount)
