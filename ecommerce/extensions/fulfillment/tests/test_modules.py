"""Tests of the Fulfillment API's fulfillment modules."""
import datetime
import json

import ddt
import httpretty
import mock
from django.test import override_settings
from oscar.core.loading import get_class, get_model
from oscar.test import factories
from oscar.test.newfactories import BasketFactory, UserFactory
from requests.exceptions import ConnectionError, Timeout
from testfixtures import LogCapture

from ecommerce.core.constants import (COUPON_PRODUCT_CLASS_NAME, ENROLLMENT_CODE_PRODUCT_CLASS_NAME,
                                      ENROLLMENT_CODE_SWITCH, SEAT_PRODUCT_CLASS_NAME)
from ecommerce.core.tests import toggle_switch
from ecommerce.core.url_utils import get_lms_enrollment_api_url
from ecommerce.coupons.tests.mixins import CouponMixin
from ecommerce.courses.models import Course
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.courses.utils import mode_for_seat
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.extensions.fulfillment.modules import (CouponFulfillmentModule, EnrollmentCodeFulfillmentModule,
                                                      EnrollmentFulfillmentModule)
from ecommerce.extensions.fulfillment.status import LINE
from ecommerce.extensions.fulfillment.tests.mixins import FulfillmentTestMixin
from ecommerce.extensions.voucher.models import OrderLineVouchers
from ecommerce.extensions.voucher.utils import create_vouchers
from ecommerce.tests.testcases import TestCase

JSON = 'application/json'
LOGGER_NAME = 'ecommerce.extensions.analytics.utils'

Applicator = get_class('offer.utils', 'Applicator')
Benefit = get_model('offer', 'Benefit')
Catalog = get_model('catalogue', 'Catalog')
Product = get_model('catalogue', 'Product')
ProductAttribute = get_model('catalogue', 'ProductAttribute')
ProductClass = get_model('catalogue', 'ProductClass')
StockRecord = get_model('partner', 'StockRecord')
Voucher = get_model('voucher', 'Voucher')


@ddt.ddt
@override_settings(EDX_API_KEY='foo')
class EnrollmentFulfillmentModuleTests(CourseCatalogTestMixin, FulfillmentTestMixin, TestCase):
    """Test course seat fulfillment."""

    course_id = 'edX/DemoX/Demo_Course'
    certificate_type = 'test-certificate-type'
    provider = None

    def setUp(self):
        super(EnrollmentFulfillmentModuleTests, self).setUp()

        self.user = UserFactory()
        self.course = Course.objects.create(id=self.course_id, name='Demo Course')

        self.seat = self.course.create_or_update_seat(self.certificate_type, False, 100, self.partner, self.provider)

        basket = BasketFactory(owner=self.user)
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
        httpretty.register_uri(httpretty.POST, get_lms_enrollment_api_url(), status=200, body='{}', content_type=JSON)
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
            'enrollment_attributes': [
                {
                    'namespace': 'order',
                    'name': 'order_number',
                    'value': self.order.number
                }
            ]
        }

        expected_headers = {
            'X-Edx-Ga-Client-Id': 'GA-123456789',
            'X-Forwarded-For': '11.22.33.44',
        }

        self.assertDictContainsSubset(expected_headers, actual_headers)
        self.assertEqual(expected_body, actual_body)

    @httpretty.activate
    @mock.patch('ecommerce.extensions.fulfillment.modules.parse_tracking_context')
    def test_enrollment_module_fulfill_order_with_discount_no_voucher(self, parse_tracking_context):
        """
        Test that components of the Fulfillment Module which trigger on the presence of a voucher do
        not cause failures in cases where a discount does not have a voucher included
        (such as with a Conditional Offer)
        """
        httpretty.register_uri(httpretty.POST, get_lms_enrollment_api_url(), status=200, body='{}', content_type=JSON)
        parse_tracking_context.return_value = ('user_123', 'GA-123456789', '11.22.33.44')
        self.create_seat_and_order(certificate_type='credit', provider='MIT')
        self.order.discounts.create()
        __, lines = EnrollmentFulfillmentModule().fulfill_product(self.order, list(self.order.lines.all()))
        # No exceptions should be raised and the order should be fulfilled
        self.assertEqual(lines[0].status, 'Complete')

    @override_settings(EDX_API_KEY=None)
    def test_enrollment_module_not_configured(self):
        """Test that lines receive a configuration error status if fulfillment configuration is invalid."""
        EnrollmentFulfillmentModule().fulfill_product(self.order, list(self.order.lines.all()))
        self.assertEqual(LINE.FULFILLMENT_CONFIGURATION_ERROR, self.order.lines.all()[0].status)

    def test_enrollment_module_fulfill_bad_attributes(self):
        """Test that use of the Fulfillment Module fails when the product does not have attributes."""
        ProductAttribute.objects.get(product_class__name=SEAT_PRODUCT_CLASS_NAME, code='course_key').delete()
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
        httpretty.register_uri(httpretty.POST, get_lms_enrollment_api_url(), status=500, body=body, content_type=JSON)
        EnrollmentFulfillmentModule().fulfill_product(self.order, list(self.order.lines.all()))
        self.assertEqual(LINE.FULFILLMENT_SERVER_ERROR, self.order.lines.all()[0].status)

    @httpretty.activate
    @mock.patch('ecommerce.extensions.fulfillment.modules.parse_tracking_context')
    def test_revoke_product(self, parse_tracking_context):
        """ The method should call the Enrollment API to un-enroll the student, and return True. """
        httpretty.register_uri(httpretty.POST, get_lms_enrollment_api_url(), status=200, body='{}', content_type=JSON)
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
        httpretty.register_uri(httpretty.POST, get_lms_enrollment_api_url(), status=400, body=body, content_type=JSON)

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
        httpretty.register_uri(httpretty.POST, get_lms_enrollment_api_url(), status=500, body=body, content_type=JSON)

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

        httpretty.register_uri(httpretty.POST, get_lms_enrollment_api_url(), body=request_callback)
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
        httpretty.register_uri(httpretty.POST, get_lms_enrollment_api_url(), status=200, body='{}', content_type=JSON)

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
                    'namespace': 'order',
                    'name': 'order_number',
                    'value': self.order.number
                },
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

    def test_voucher_usage(self):
        """
        Test that using a voucher applies offer discount to reduce order price
        """
        catalog = Catalog.objects.create(partner=self.partner)

        coupon_product_class, _ = ProductClass.objects.get_or_create(name=COUPON_PRODUCT_CLASS_NAME)
        coupon = factories.create_product(
            product_class=coupon_product_class,
            title='Test product'
        )

        stock_record = StockRecord.objects.filter(product=self.seat).first()
        catalog.stock_records.add(stock_record)

        vouchers = create_vouchers(
            benefit_type=Benefit.PERCENTAGE,
            benefit_value=100.00,
            catalog=catalog,
            coupon=coupon,
            end_datetime=datetime.datetime.now() + datetime.timedelta(days=30),
            enterprise_customer=None,
            name="Test Voucher",
            quantity=10,
            start_datetime=datetime.datetime.now(),
            voucher_type=Voucher.SINGLE_USE
        )
        voucher = vouchers[0]

        seat_basket = self.order.basket
        Applicator().apply_offers(seat_basket, voucher.offers.all())
        self.assertEqual(seat_basket.total_excl_tax, 0.00)


class CouponFulfillmentModuleTest(CouponMixin, FulfillmentTestMixin, TestCase):
    """ Test coupon fulfillment. """

    def setUp(self):
        super(CouponFulfillmentModuleTest, self).setUp()
        coupon = self.create_coupon()
        user = UserFactory()
        basket = BasketFactory()
        basket.add_product(coupon, 1)
        self.order = factories.create_order(number=1, basket=basket, user=user)

    def test_supports_line(self):
        """Test that a line containing Coupon returns True."""
        line = self.order.lines.first()
        supports_line = CouponFulfillmentModule().supports_line(line)
        self.assertTrue(supports_line)

    def test_get_supported_lines(self):
        """Test that Coupon lines where returned."""
        lines = self.order.lines.all()
        supported_lines = CouponFulfillmentModule().get_supported_lines(lines)
        self.assertEqual(len(supported_lines), 1)

    def test_fulfill_product(self):
        """Test fulfilling a Coupon product."""
        lines = self.order.lines.all()
        __, completed_lines = CouponFulfillmentModule().fulfill_product(self.order, lines)
        self.assertEqual(completed_lines[0].status, LINE.COMPLETE)

    def test_revoke_line(self):
        line = self.order.lines.first()
        with self.assertRaises(NotImplementedError):
            CouponFulfillmentModule().revoke_line(line)


class EnrollmentCodeFulfillmentModuleTests(CourseCatalogTestMixin, TestCase):
    """ Test Enrollment code fulfillment. """
    QUANTITY = 5

    def setUp(self):
        super(EnrollmentCodeFulfillmentModuleTests, self).setUp()
        toggle_switch(ENROLLMENT_CODE_SWITCH, True)
        self.toggle_ecommerce_receipt_page(True)
        course = CourseFactory()
        course.create_or_update_seat('verified', True, 50, self.partner, create_enrollment_code=True)
        enrollment_code = Product.objects.get(product_class__name=ENROLLMENT_CODE_PRODUCT_CLASS_NAME)
        user = UserFactory()
        basket = BasketFactory()
        basket.add_product(enrollment_code, self.QUANTITY)
        self.order = factories.create_order(number=1, basket=basket, user=user)

    def test_supports_line(self):
        """Test that support_line returns True for Enrollment code lines."""
        line = self.order.lines.first()
        supports_line = EnrollmentCodeFulfillmentModule().supports_line(line)
        self.assertTrue(supports_line)

        order = factories.create_order()
        unsupported_line = order.lines.first()
        supports_line = EnrollmentCodeFulfillmentModule().supports_line(unsupported_line)
        self.assertFalse(supports_line)

    def test_get_supported_lines(self):
        """Test that Enrollment code lines where returned."""
        lines = self.order.lines.all()
        supported_lines = EnrollmentCodeFulfillmentModule().get_supported_lines(lines)
        self.assertListEqual(supported_lines, list(lines))

    def test_fulfill_product(self):
        """Test fulfilling an Enrollment code product."""
        self.assertEqual(OrderLineVouchers.objects.count(), 0)
        lines = self.order.lines.all()
        __, completed_lines = EnrollmentCodeFulfillmentModule().fulfill_product(self.order, lines)
        self.assertEqual(completed_lines[0].status, LINE.COMPLETE)
        self.assertEqual(OrderLineVouchers.objects.count(), 1)
        self.assertEqual(OrderLineVouchers.objects.first().vouchers.count(), self.QUANTITY)

    def test_fulfill_product_with_lms_receipt_page(self):
        """Test disabling otto_receipt_page switch still results in successfully fulfilling Enrollment code product."""
        self.site.siteconfiguration.enable_otto_receipt_page = False
        self.assertEqual(OrderLineVouchers.objects.count(), 0)
        lines = self.order.lines.all()
        __, completed_lines = EnrollmentCodeFulfillmentModule().fulfill_product(self.order, lines)
        self.assertEqual(completed_lines[0].status, LINE.COMPLETE)
        self.assertEqual(OrderLineVouchers.objects.count(), 1)
        self.assertEqual(OrderLineVouchers.objects.first().vouchers.count(), self.QUANTITY)

    def test_revoke_line(self):
        line = self.order.lines.first()
        with self.assertRaises(NotImplementedError):
            EnrollmentCodeFulfillmentModule().revoke_line(line)
