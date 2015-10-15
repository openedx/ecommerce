"""Tests of the Fulfillment API's fulfillment modules."""
import json

import ddt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
import httpretty
import mock
from oscar.core.loading import get_model
from oscar.test import factories
from oscar.test.newfactories import UserFactory, BasketFactory
from requests.exceptions import ConnectionError, Timeout
from testfixtures import LogCapture

from ecommerce.courses.models import Course
from ecommerce.courses.utils import mode_for_seat
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.extensions.fulfillment.modules import EnrollmentFulfillmentModule
from ecommerce.extensions.fulfillment.status import LINE
from ecommerce.extensions.fulfillment.tests.mixins import FulfillmentTestMixin
from ecommerce.tests.mixins import PartnerMixin

JSON = 'application/json'
LOGGER_NAME = 'ecommerce.extensions.analytics.utils'

ProductAttribute = get_model("catalogue", "ProductAttribute")
User = get_user_model()


@ddt.ddt
@override_settings(EDX_API_KEY='foo')
class EnrollmentFulfillmentModuleTests(CourseCatalogTestMixin, FulfillmentTestMixin, PartnerMixin, TestCase):
    """Test course seat fulfillment."""

    course_id = 'edX/DemoX/Demo_Course'
    certificate_type = 'test-certificate-type'
    provider = None

    def setUp(self):
        super(EnrollmentFulfillmentModuleTests, self).setUp()

        self.user = UserFactory()
        self.course = Course.objects.create(id=self.course_id, name='Demo Course')
        self.partner = self.create_partner('edx')

        self.seat = self.course.create_or_update_seat(self.certificate_type, False, 100, self.partner, self.provider)

        basket = BasketFactory()
        basket.add_product(self.seat, 1)
        self.order = factories.create_order(number=1, basket=basket, user=self.user)

    # pylint: disable=attribute-defined-outside-init
    def create_seat_and_order(self, certificate_type='test-certificate-type', provider=None):
        """ Create the certificate of given type and seat of given provider.

        Arguments:
            certificate_type(str): The type of certificate
            provider(str): The provider ID.
        Returns:
            None
        """
        self.certificate_type = certificate_type
        self.provider = provider
        self.seat = self.course.create_or_update_seat(self.certificate_type, False, 100, self.partner, self.provider)

        basket = BasketFactory()
        basket.add_product(self.seat, 1)
        self.order = factories.create_order(number=2, basket=basket, user=self.user)

    def test_enrollment_module_support(self):
        """Test that we get the correct values back for supported product lines."""
        supported_lines = EnrollmentFulfillmentModule().get_supported_lines(list(self.order.lines.all()))
        self.assertEqual(1, len(supported_lines))

    @httpretty.activate
    @mock.patch('ecommerce.extensions.fulfillment.modules.parse_tracking_context')
    def test_enrollment_module_fulfill(self, parse_tracking_context):
        """Happy path test to ensure we can properly fulfill enrollments."""
        httpretty.register_uri(httpretty.POST, settings.ENROLLMENT_API_URL, status=200, body='{}', content_type=JSON)
        parse_tracking_context.return_value = ('user_123', 'GA-123456789', '11.22.33.44')
        # Attempt to enroll.
        with LogCapture(LOGGER_NAME) as l:
            EnrollmentFulfillmentModule().fulfill_product(self.order, list(self.order.lines.all()))

            line = self.order.lines.get()
            l.check(
                (
                    LOGGER_NAME,
                    'INFO',
                    'line_fulfilled: course_id="{}", credit_provider="{}", mode="{}", order_line_id="{}", '
                    'order_number="{}", product_class="{}", user_id="{}"'.format(
                        line.product.attr.course_key,
                        None,
                        mode_for_seat(line.product),
                        line.id,
                        line.order.number,
                        line.product.get_product_class().name,
                        line.order.user.id,
                    )
                )
            )

        self.assertEqual(LINE.COMPLETE, line.status)

        last_request = httpretty.last_request()
        actual_body = json.loads(last_request.body)
        actual_headers = last_request.headers

        expected_body = {
            'user': self.order.user.username,
            'is_active': True,
            'mode': self.certificate_type,
            'course_details': {
                'course_id': self.course_id,
            },
            'enrollment_attributes': []
        }

        expected_headers = {
            'X-Edx-Ga-Client-Id': 'GA-123456789',
            'X-Forwarded-For': '11.22.33.44',
        }

        self.assertDictContainsSubset(expected_headers, actual_headers)
        self.assertEqual(expected_body, actual_body)

    @override_settings(ENROLLMENT_API_URL='')
    def test_enrollment_module_not_configured(self):
        """Test that lines receive a configuration error status if fulfillment configuration is invalid."""
        EnrollmentFulfillmentModule().fulfill_product(self.order, list(self.order.lines.all()))
        self.assertEqual(LINE.FULFILLMENT_CONFIGURATION_ERROR, self.order.lines.all()[0].status)

    def test_enrollment_module_fulfill_bad_attributes(self):
        """Test that use of the Fulfillment Module fails when the product does not have attributes."""
        ProductAttribute.objects.get(code='course_key').delete()
        EnrollmentFulfillmentModule().fulfill_product(self.order, list(self.order.lines.all()))
        self.assertEqual(LINE.FULFILLMENT_CONFIGURATION_ERROR, self.order.lines.all()[0].status)

    @mock.patch('requests.post', mock.Mock(side_effect=ConnectionError))
    def test_enrollment_module_network_error(self):
        """Test that lines receive a network error status if a fulfillment request experiences a network error."""
        EnrollmentFulfillmentModule().fulfill_product(self.order, list(self.order.lines.all()))
        self.assertEqual(LINE.FULFILLMENT_NETWORK_ERROR, self.order.lines.all()[0].status)

    @mock.patch('requests.post', mock.Mock(side_effect=Timeout))
    def test_enrollment_module_request_timeout(self):
        """Test that lines receive a timeout error status if a fulfillment request times out."""
        EnrollmentFulfillmentModule().fulfill_product(self.order, list(self.order.lines.all()))
        self.assertEqual(LINE.FULFILLMENT_TIMEOUT_ERROR, self.order.lines.all()[0].status)

    @httpretty.activate
    @ddt.data(None, '{"message": "Oops!"}')
    def test_enrollment_module_server_error(self, body):
        """Test that lines receive a server-side error status if a server-side error occurs during fulfillment."""
        # NOTE: We are testing for cases where the response does and does NOT have data. The module should be able
        # to handle both cases.
        httpretty.register_uri(httpretty.POST, settings.ENROLLMENT_API_URL, status=500, body=body, content_type=JSON)
        EnrollmentFulfillmentModule().fulfill_product(self.order, list(self.order.lines.all()))
        self.assertEqual(LINE.FULFILLMENT_SERVER_ERROR, self.order.lines.all()[0].status)

    @httpretty.activate
    @mock.patch('ecommerce.extensions.fulfillment.modules.parse_tracking_context')
    def test_revoke_product(self, parse_tracking_context):
        """ The method should call the Enrollment API to un-enroll the student, and return True. """
        httpretty.register_uri(httpretty.POST, settings.ENROLLMENT_API_URL, status=200, body='{}', content_type=JSON)
        parse_tracking_context.return_value = ('user_123', 'GA-123456789', '11.22.33.44')
        line = self.order.lines.first()

        with LogCapture(LOGGER_NAME) as l:
            self.assertTrue(EnrollmentFulfillmentModule().revoke_line(line))

            l.check(
                (
                    LOGGER_NAME,
                    'INFO',
                    'line_revoked: certificate_type="{}", course_id="{}", order_line_id="{}", order_number="{}", '
                    'product_class="{}", user_id="{}"'.format(
                        getattr(line.product.attr, 'certificate_type', ''),
                        line.product.attr.course_key,
                        line.id,
                        line.order.number,
                        line.product.get_product_class().name,
                        line.order.user.id
                    )
                )
            )

        last_request = httpretty.last_request()
        actual_body = json.loads(last_request.body)
        actual_headers = last_request.headers

        expected_body = {
            'user': self.order.user.username,
            'is_active': False,
            'mode': self.certificate_type,
            'course_details': {
                'course_id': self.course_id,
            },
        }

        expected_headers = {
            'X-Edx-Ga-Client-Id': 'GA-123456789',
            'X-Forwarded-For': '11.22.33.44',
        }

        self.assertDictContainsSubset(expected_headers, actual_headers)
        self.assertEqual(expected_body, actual_body)

    @httpretty.activate
    def test_revoke_product_expected_error(self):
        """
        If the Enrollment API responds with an expected error, the method should log that revocation was
        bypassed, and return True.
        """
        message = 'Enrollment mode mismatch: active mode=x, requested mode=y. Won\'t deactivate.'
        body = '{{"message": "{}"}}'.format(message)
        httpretty.register_uri(httpretty.POST, settings.ENROLLMENT_API_URL, status=400, body=body, content_type=JSON)

        line = self.order.lines.first()
        logger_name = 'ecommerce.extensions.fulfillment.modules'
        with LogCapture(logger_name) as l:
            self.assertTrue(EnrollmentFulfillmentModule().revoke_line(line))
            l.check(
                (logger_name, 'INFO', 'Attempting to revoke fulfillment of Line [{}]...'.format(line.id)),
                (logger_name, 'INFO', 'Skipping revocation for line [%d]: %s' % (line.id, message))
            )

    @httpretty.activate
    def test_revoke_product_unexpected_error(self):
        """ If the Enrollment API responds with a non-200 status, the method should log an error and return False. """
        message = 'Meh.'
        body = '{{"message": "{}"}}'.format(message)
        httpretty.register_uri(httpretty.POST, settings.ENROLLMENT_API_URL, status=500, body=body, content_type=JSON)

        line = self.order.lines.first()
        logger_name = 'ecommerce.extensions.fulfillment.modules'
        with LogCapture(logger_name) as l:
            self.assertFalse(EnrollmentFulfillmentModule().revoke_line(line))
            l.check(
                (logger_name, 'INFO', 'Attempting to revoke fulfillment of Line [{}]...'.format(line.id)),
                (logger_name, 'ERROR', 'Failed to revoke fulfillment of Line [%d]: %s' % (line.id, message))
            )

    @httpretty.activate
    def test_revoke_product_unknown_exception(self):
        """
        If an exception is raised while contacting the Enrollment API, the method should log an error and return False.
        """

        def request_callback(_method, _uri, _headers):
            raise Timeout

        httpretty.register_uri(httpretty.POST, settings.ENROLLMENT_API_URL, body=request_callback)
        line = self.order.lines.first()
        logger_name = 'ecommerce.extensions.fulfillment.modules'

        with LogCapture(logger_name) as l:
            self.assertFalse(EnrollmentFulfillmentModule().revoke_line(line))
            l.check(
                (logger_name, 'INFO', 'Attempting to revoke fulfillment of Line [{}]...'.format(line.id)),
                (logger_name, 'ERROR', 'Failed to revoke fulfillment of Line [{}].'.format(line.id))
            )

    @httpretty.activate
    def test_credit_enrollment_module_fulfill(self):
        """Happy path test to ensure we can properly fulfill enrollments."""
        # Create the credit certificate type and order for the credit certificate type.
        self.create_seat_and_order(certificate_type='credit', provider='MIT')
        httpretty.register_uri(httpretty.POST, settings.ENROLLMENT_API_URL, status=200, body='{}', content_type=JSON)

        # Attempt to enroll.
        with LogCapture(LOGGER_NAME) as l:
            EnrollmentFulfillmentModule().fulfill_product(self.order, list(self.order.lines.all()))

            line = self.order.lines.get()
            l.check(
                (
                    LOGGER_NAME,
                    'INFO',
                    'line_fulfilled: course_id="{}", credit_provider="{}", mode="{}", order_line_id="{}", '
                    'order_number="{}", product_class="{}", user_id="{}"'.format(
                        line.product.attr.course_key,
                        line.product.attr.credit_provider,
                        mode_for_seat(line.product),
                        line.id,
                        line.order.number,
                        line.product.get_product_class().name,
                        line.order.user.id,
                    )
                )
            )

        self.assertEqual(LINE.COMPLETE, line.status)

        actual = json.loads(httpretty.last_request().body)
        expected = {
            'user': self.order.user.username,
            'is_active': True,
            'mode': self.certificate_type,
            'course_details': {
                'course_id': self.course_id,
            },
            'enrollment_attributes': [
                {
                    'namespace': 'credit',
                    'name': 'provider_id',
                    'value': self.provider
                }
            ]
        }
        self.assertEqual(actual, expected)

    def test_enrollment_headers(self):
        """ Test that the enrollment module 'EnrollmentFulfillmentModule' is
        sending enrollment request over to the LMS with proper headers.
        """
        # Create a dummy data for the enrollment request.
        data = {
            'user': 'test',
            'is_active': True,
            'mode': 'honor',
            'course_details': {
                'course_id': self.course_id
            },
            'enrollment_attributes': []
        }

        # Create a dummy user and attach the tracking_context
        user = UserFactory()
        user.tracking_context = {'lms_user_id': '1', 'lms_client_id': '123.123', 'lms_ip': '11.22.33.44'}

        # Now call the enrollment api to send POST request to LMS and verify
        # that the header of the request being sent contains the analytics
        # header 'x-edx-ga-client-id'.
        # This will raise the exception 'ConnectionError' because the LMS is
        # not available for ecommerce tests.
        try:
            # pylint: disable=protected-access
            EnrollmentFulfillmentModule()._post_to_enrollment_api(data=data, user=user)
        except ConnectionError as exp:
            # Check that the enrollment request object has the analytics header
            # 'x-edx-ga-client-id' and 'x-forwarded-for'.
            self.assertEqual(exp.request.headers.get('x-edx-ga-client-id'), '123.123')
            self.assertEqual(exp.request.headers.get('x-forwarded-for'), '11.22.33.44')
