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
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.extensions.fulfillment.modules import EnrollmentFulfillmentModule
from ecommerce.extensions.fulfillment.status import LINE
from ecommerce.extensions.fulfillment.tests.mixins import FulfillmentTestMixin

JSON = 'application/json'
LOGGER_NAME = 'ecommerce.extensions.analytics.utils'

ProductAttribute = get_model("catalogue", "ProductAttribute")
User = get_user_model()


class EnrollmentFulfillmentTestMixin(CourseCatalogTestMixin, FulfillmentTestMixin):
    certificate_type = 'test-certificate-type'
    course_id = 'edX/DemoX/Demo_Course'
    provider = None

    def setUp(self):
        super(EnrollmentFulfillmentTestMixin, self).setUp()

        user = UserFactory()
        course = Course.objects.create(id=self.course_id, name='Demo Course')
        self.seat = course.create_or_update_seat(self.certificate_type, False, 100, self.provider)

        basket = BasketFactory()
        basket.add_product(self.seat, 1)
        self.order = factories.create_order(number=1, basket=basket, user=user)


@ddt.ddt
@override_settings(EDX_API_KEY='foo')
class EnrollmentFulfillmentModuleTests(EnrollmentFulfillmentTestMixin, TestCase):
    """Test course seat fulfillment."""

    def test_enrollment_module_support(self):
        """Test that we get the correct values back for supported product lines."""
        supported_lines = EnrollmentFulfillmentModule().get_supported_lines(list(self.order.lines.all()))
        self.assertEqual(1, len(supported_lines))

    @httpretty.activate
    def test_enrollment_module_fulfill(self):
        """Happy path test to ensure we can properly fulfill enrollments."""
        httpretty.register_uri(httpretty.POST, settings.ENROLLMENT_API_URL, status=200, body='{}', content_type=JSON)
        # Attempt to enroll.
        with LogCapture(LOGGER_NAME) as l:
            EnrollmentFulfillmentModule().fulfill_product(self.order, list(self.order.lines.all()))

            line = self.order.lines.get()
            l.check(
                (
                    LOGGER_NAME,
                    'INFO',
                    'line_fulfilled: certificate_type="{}", course_id="{}", credit_provider="{}", order_line_id="{}", '
                    'order_number="{}", product_class="{}", user_id="{}"'.format(
                        line.product.attr.certificate_type,
                        line.product.attr.course_key,
                        None,
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
            'enrollment_attributes': []
        }
        self.assertEqual(actual, expected)

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
    def test_revoke_product(self):
        """ The method should call the Enrollment API to un-enroll the student, and return True. """
        httpretty.register_uri(httpretty.POST, settings.ENROLLMENT_API_URL, status=200, body='{}', content_type=JSON)
        line = self.order.lines.first()

        with LogCapture(LOGGER_NAME) as l:
            self.assertTrue(EnrollmentFulfillmentModule().revoke_line(line))

            l.check(
                (
                    LOGGER_NAME,
                    'INFO',
                    'line_revoked: certificate_type="{}", course_id="{}", order_line_id="{}", order_number="{}", '
                    'product_class="{}", user_id="{}"'.format(
                        line.product.attr.certificate_type,
                        line.product.attr.course_key,
                        line.id,
                        line.order.number,
                        line.product.get_product_class().name,
                        line.order.user.id
                    )
                )
            )

        actual = json.loads(httpretty.last_request().body)
        expected = {
            'user': self.order.user.username,
            'is_active': False,
            'mode': self.certificate_type,
            'course_details': {
                'course_id': self.course_id,
            },
        }
        self.assertEqual(actual, expected)

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


@ddt.ddt
@override_settings(EDX_API_KEY='foo')
class EnrollmentFulfillmentCreditSeatModuleTests(EnrollmentFulfillmentTestMixin, TestCase):
    """Test course seat fulfillment."""
    certificate_type = 'credit'
    provider = 'MIT'

    @httpretty.activate
    def test_enrollment_module_fulfill(self):
        """Happy path test to ensure we can properly fulfill enrollments."""
        httpretty.register_uri(httpretty.POST, settings.ENROLLMENT_API_URL, status=200, body='{}', content_type=JSON)

        # Attempt to enroll.
        with LogCapture(LOGGER_NAME) as l:
            EnrollmentFulfillmentModule().fulfill_product(self.order, list(self.order.lines.all()))

            line = self.order.lines.get()
            l.check(
                (
                    LOGGER_NAME,
                    'INFO',
                    'line_fulfilled: certificate_type="{}", course_id="{}", credit_provider="{}", order_line_id="{}", '
                    'order_number="{}", product_class="{}", user_id="{}"'.format(
                        line.product.attr.certificate_type,
                        line.product.attr.course_key,
                        line.product.attr.credit_provider,
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
