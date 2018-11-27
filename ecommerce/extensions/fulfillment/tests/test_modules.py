"""Tests of the Fulfillment API's fulfillment modules."""
import datetime
import json
import uuid

import ddt
import httpretty
import mock
from django.test import override_settings
from oscar.core.loading import get_class, get_model
from oscar.test import factories
from requests.exceptions import ConnectionError, Timeout
from testfixtures import LogCapture

from ecommerce.core.constants import (
    COUPON_PRODUCT_CLASS_NAME,
    COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME,
    DONATIONS_FROM_CHECKOUT_TESTS_PRODUCT_TYPE_NAME,
    ENROLLMENT_CODE_PRODUCT_CLASS_NAME,
    SEAT_PRODUCT_CLASS_NAME
)
from ecommerce.core.url_utils import get_lms_enrollment_api_url, get_lms_entitlement_api_url
from ecommerce.coupons.tests.mixins import CouponMixin
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.courses.utils import mode_for_product
from ecommerce.entitlements.utils import create_or_update_course_entitlement
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.extensions.fulfillment.modules import (
    CouponFulfillmentModule,
    CourseEntitlementFulfillmentModule,
    DonationsFromCheckoutTestFulfillmentModule,
    EnrollmentCodeFulfillmentModule,
    EnrollmentFulfillmentModule
)
from ecommerce.extensions.fulfillment.status import LINE
from ecommerce.extensions.fulfillment.tests.mixins import FulfillmentTestMixin
from ecommerce.extensions.test.factories import create_order
from ecommerce.extensions.voucher.models import OrderLineVouchers
from ecommerce.extensions.voucher.utils import create_vouchers
from ecommerce.programs.tests.mixins import ProgramTestMixin
from ecommerce.tests.testcases import TestCase

JSON = 'application/json'
LOGGER_NAME = 'ecommerce.extensions.analytics.utils'

Benefit = get_model('offer', 'Benefit')
Catalog = get_model('catalogue', 'Catalog')
CustomApplicator = get_class('offer.applicator', 'CustomApplicator')
Option = get_model('catalogue', 'Option')
Product = get_model('catalogue', 'Product')
ProductAttribute = get_model('catalogue', 'ProductAttribute')
ProductClass = get_model('catalogue', 'ProductClass')
StockRecord = get_model('partner', 'StockRecord')
Voucher = get_model('voucher', 'Voucher')


@ddt.ddt
@override_settings(EDX_API_KEY='foo')
class EnrollmentFulfillmentModuleTests(ProgramTestMixin, DiscoveryTestMixin, FulfillmentTestMixin, TestCase):
    """Test course seat fulfillment."""

    course_id = 'edX/DemoX/Demo_Course'
    certificate_type = 'test-certificate-type'
    provider = None

    def setUp(self):
        super(EnrollmentFulfillmentModuleTests, self).setUp()

        self.user = factories.UserFactory()
        self.user.tracking_context = {
            'ga_client_id': 'test-client-id', 'lms_user_id': 'test-user-id', 'lms_ip': '127.0.0.1'
        }
        self.user.save()
        self.course = CourseFactory(id=self.course_id, name='Demo Course', partner=self.partner)

        self.seat = self.course.create_or_update_seat(self.certificate_type, False, 100, self.provider)

        basket = factories.BasketFactory(owner=self.user, site=self.site)
        basket.add_product(self.seat, 1)
        self.order = create_order(number=1, basket=basket, user=self.user)

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
        self.seat = self.course.create_or_update_seat(self.certificate_type, False, 100, self.provider)

        basket = factories.BasketFactory(owner=self.user, site=self.site)
        basket.add_product(self.seat, 1)
        self.order = create_order(number=2, basket=basket, user=self.user)

    def prepare_basket_with_voucher(self, program_uuid=None):
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
            enterprise_customer_catalog=None,
            name="Test Voucher",
            quantity=10,
            start_datetime=datetime.datetime.now(),
            voucher_type=Voucher.SINGLE_USE,
            program_uuid=program_uuid,
        )
        CustomApplicator().apply_offers(self.order.basket, vouchers[0].offers.all())

    def test_enrollment_module_support(self):
        """Test that we get the correct values back for supported product lines."""
        supported_lines = EnrollmentFulfillmentModule().get_supported_lines(list(self.order.lines.all()))
        self.assertEqual(1, len(supported_lines))

    @httpretty.activate
    def test_enrollment_module_fulfill(self):
        """Happy path test to ensure we can properly fulfill enrollments."""
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
                        None,
                        mode_for_product(line.product),
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
            'X-Edx-Ga-Client-Id': self.user.tracking_context['ga_client_id'],
            'X-Forwarded-For': self.user.tracking_context['lms_ip'],
        }

        self.assertDictContainsSubset(expected_headers, actual_headers)
        self.assertEqual(expected_body, actual_body)

    @httpretty.activate
    def test_enrollment_module_fulfill_order_with_discount_no_voucher(self):
        """
        Test that components of the Fulfillment Module which trigger on the presence of a voucher do
        not cause failures in cases where a discount does not have a voucher included
        (such as with a Conditional Offer)
        """
        httpretty.register_uri(httpretty.POST, get_lms_enrollment_api_url(), status=200, body='{}', content_type=JSON)
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
    def test_revoke_product(self):
        """ The method should call the Enrollment API to un-enroll the student, and return True. """
        httpretty.register_uri(httpretty.POST, get_lms_enrollment_api_url(), status=200, body='{}', content_type=JSON)
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
            'X-Edx-Ga-Client-Id': self.user.tracking_context['ga_client_id'],
            'X-Forwarded-For': self.user.tracking_context['lms_ip'],
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
                        mode_for_product(line.product),
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

        # Now call the enrollment api to send POST request to LMS and verify
        # that the header of the request being sent contains the analytics
        # header 'x-edx-ga-client-id'.
        # This will raise the exception 'ConnectionError' because the LMS is
        # not available for ecommerce tests.
        try:
            # pylint: disable=protected-access
            EnrollmentFulfillmentModule()._post_to_enrollment_api(data=data, user=self.user)
        except ConnectionError as exp:
            # Check that the enrollment request object has the analytics header
            # 'x-edx-ga-client-id' and 'x-forwarded-for'.
            self.assertEqual(exp.request.headers.get('x-edx-ga-client-id'), self.user.tracking_context['ga_client_id'])
            self.assertEqual(exp.request.headers.get('x-forwarded-for'), self.user.tracking_context['lms_ip'])

    def test_voucher_usage(self):
        """
        Test that using a voucher applies offer discount to reduce order price
        """
        self.prepare_basket_with_voucher()
        self.assertEqual(self.order.basket.total_excl_tax, 0.00)

    @httpretty.activate
    def test_voucher_usage_with_program(self):
        """
        Test that using a voucher with a program basket results in a fulfilled order.
        """
        httpretty.register_uri(httpretty.POST, get_lms_enrollment_api_url(), status=200, body='{}', content_type=JSON)
        self.create_seat_and_order(certificate_type='credit', provider='MIT')
        program_uuid = uuid.uuid4()
        self.mock_program_detail_endpoint(program_uuid, self.site_configuration.discovery_api_url)
        self.mock_user_data(self.user.username)
        self.prepare_basket_with_voucher(program_uuid=program_uuid)
        __, lines = EnrollmentFulfillmentModule().fulfill_product(self.order, list(self.order.lines.all()))
        # No exceptions should be raised and the order should be fulfilled
        self.assertEqual(lines[0].status, 'Complete')


class CouponFulfillmentModuleTest(CouponMixin, FulfillmentTestMixin, TestCase):
    """ Test coupon fulfillment. """

    def setUp(self):
        super(CouponFulfillmentModuleTest, self).setUp()
        coupon = self.create_coupon()
        user = factories.UserFactory()
        basket = factories.BasketFactory(owner=user, site=self.site)
        basket.add_product(coupon, 1)
        self.order = create_order(number=1, basket=basket, user=user)

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


class DonationsFromCheckoutTestFulfillmentModuleTest(FulfillmentTestMixin, TestCase):
    """ Test donation fulfillment. """

    def setUp(self):
        super(DonationsFromCheckoutTestFulfillmentModuleTest, self).setUp()
        donation_class = ProductClass.objects.get(
            name=DONATIONS_FROM_CHECKOUT_TESTS_PRODUCT_TYPE_NAME,
            track_stock=False
        )
        donation = factories.create_product(
            product_class=donation_class,
            title='Test product'
        )
        user = factories.UserFactory()
        basket = factories.BasketFactory(owner=user, site=self.site)
        factories.create_stockrecord(donation, num_in_stock=2, price_excl_tax=10)
        basket.add_product(donation, 1)
        self.order = create_order(number=1, basket=basket, user=user)

    def test_supports_line(self):
        """Test that a line containing Coupon returns True."""
        line = self.order.lines.first()
        supports_line = DonationsFromCheckoutTestFulfillmentModule().supports_line(line)
        self.assertTrue(supports_line)

    def test_get_supported_lines(self):
        """Test that Coupon lines where returned."""
        lines = self.order.lines.all()
        supported_lines = DonationsFromCheckoutTestFulfillmentModule().get_supported_lines(lines)
        self.assertEqual(len(supported_lines), 1)

    def test_fulfill_product(self):
        """Test fulfilling a Coupon product."""
        lines = self.order.lines.all()
        __, completed_lines = DonationsFromCheckoutTestFulfillmentModule().fulfill_product(self.order, lines)
        self.assertEqual(completed_lines[0].status, LINE.COMPLETE)

    def test_revoke_line(self):
        line = self.order.lines.first()
        self.assertTrue(DonationsFromCheckoutTestFulfillmentModule().revoke_line(line))


class EnrollmentCodeFulfillmentModuleTests(DiscoveryTestMixin, TestCase):
    """ Test Enrollment code fulfillment. """
    QUANTITY = 5

    def setUp(self):
        super(EnrollmentCodeFulfillmentModuleTests, self).setUp()
        course = CourseFactory(partner=self.partner)
        course.create_or_update_seat('verified', True, 50, create_enrollment_code=True)
        enrollment_code = Product.objects.get(product_class__name=ENROLLMENT_CODE_PRODUCT_CLASS_NAME)
        user = factories.UserFactory()
        basket = factories.BasketFactory(owner=user, site=self.site)
        basket.add_product(enrollment_code, self.QUANTITY)
        self.order = create_order(number=1, basket=basket, user=user)

    def test_supports_line(self):
        """Test that support_line returns True for Enrollment code lines."""
        line = self.order.lines.first()
        supports_line = EnrollmentCodeFulfillmentModule().supports_line(line)
        self.assertTrue(supports_line)

        order = create_order()
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
        self.assertIsNotNone(OrderLineVouchers.objects.first().vouchers.first().benefit.range.catalog)

    def test_revoke_line(self):
        line = self.order.lines.first()
        with self.assertRaises(NotImplementedError):
            EnrollmentCodeFulfillmentModule().revoke_line(line)


class EntitlementFulfillmentModuleTests(FulfillmentTestMixin, TestCase):
    """ Test Course Entitlement Fulfillment """

    def setUp(self):
        super(EntitlementFulfillmentModuleTests, self).setUp()
        self.user = factories.UserFactory()
        self.course_entitlement = create_or_update_course_entitlement(
            'verified', 100, self.partner, '111-222-333-444', 'Course Entitlement')
        basket = factories.BasketFactory(owner=self.user, site=self.site)
        basket.add_product(self.course_entitlement, 1)
        self.entitlement_option = Option.objects.get(name='Course Entitlement')
        self.order = create_order(number=1, basket=basket, user=self.user)
        self.logger_name = 'ecommerce.extensions.fulfillment.modules'
        self.return_data = {
            "user": "honor",
            "course_uuid": "3b3123b8-d34b-44d8-9bbb-a12676e97123",
            "uuid": "111-222-333",
            "mode": "verified",
            "expired_at": "None"
        }

    def test_entitlement_supported_line(self):
        """ Test that support_line returns True for Course Entitlement lines. """
        line = self.order.lines.first()
        supports_line = CourseEntitlementFulfillmentModule().supports_line(line)
        self.assertTrue(supports_line)

        order = create_order()
        unsupported_line = order.lines.first()
        supports_line = CourseEntitlementFulfillmentModule().supports_line(unsupported_line)
        self.assertFalse(supports_line)

    def test_get_entitlement_supported_lines(self):
        """ Test that Course Entitlement products lines are returned. """
        lines = self.order.lines.all()
        supported_lines = CourseEntitlementFulfillmentModule().get_supported_lines(lines)
        self.assertListEqual(supported_lines, list(lines))

    @httpretty.activate
    def test_entitlement_module_fulfill(self):
        """ Test to ensure we can properly fulfill course entitlements. """

        self.mock_access_token_response()
        httpretty.register_uri(httpretty.POST, get_lms_entitlement_api_url() +
                               'entitlements/', status=200, body=json.dumps(self.return_data),
                               content_type='application/json')

        # Attempt to fulfill entitlement.
        with LogCapture(LOGGER_NAME) as l:
            CourseEntitlementFulfillmentModule().fulfill_product(self.order, list(self.order.lines.all()))

            line = self.order.lines.get()
            l.check(
                (
                    LOGGER_NAME,
                    'INFO',
                    'line_fulfilled: UUID="{}", mode="{}", order_line_id="{}", '
                    'order_number="{}", product_class="{}", user_id="{}"'.format(
                        line.product.attr.UUID,
                        mode_for_product(line.product),
                        line.id,
                        line.order.number,
                        line.product.get_product_class().name,
                        line.order.user.id,
                    )
                )
            )

            course_entitlement_uuid = line.attributes.get(option=self.entitlement_option).value
            self.assertEqual(course_entitlement_uuid, '111-222-333')
            self.assertEqual(LINE.COMPLETE, line.status)

    @httpretty.activate
    def test_entitlement_module_revoke(self):
        """ Test to revoke a Course Entitlement. """
        self.mock_access_token_response()
        httpretty.register_uri(httpretty.POST, get_lms_entitlement_api_url() +
                               'entitlements/', status=200, body=json.dumps(self.return_data),
                               content_type='application/json')

        httpretty.register_uri(httpretty.DELETE, get_lms_entitlement_api_url() +
                               'entitlements/111-222-333/', status=200, body={}, content_type='application/json')

        line = self.order.lines.first()

        # Fulfill order first to ensure we have all the line attributes set
        CourseEntitlementFulfillmentModule().fulfill_product(self.order, list(self.order.lines.all()))

        with LogCapture(LOGGER_NAME) as l:
            self.assertTrue(CourseEntitlementFulfillmentModule().revoke_line(line))

            l.check(
                (
                    LOGGER_NAME,
                    'INFO',
                    'line_revoked: UUID="{}", certificate_type="{}", order_line_id="{}", order_number="{}", '
                    'product_class="{}", user_id="{}"'.format(
                        line.product.attr.UUID,
                        getattr(line.product.attr, 'certificate_type', ''),
                        line.id,
                        line.order.number,
                        line.product.get_product_class().name,
                        line.order.user.id
                    )
                )
            )

    @httpretty.activate
    def test_entitlement_module_revoke_error(self):
        """ Test to handle an error when revoking a Course Entitlement. """
        self.mock_access_token_response()

        httpretty.register_uri(httpretty.DELETE, get_lms_entitlement_api_url() +
                               'entitlements/111-222-333/', status=500, body={}, content_type='application/json')

        line = self.order.lines.first()

        self.assertFalse(CourseEntitlementFulfillmentModule().revoke_line(line))

    @httpretty.activate
    def test_entitlement_module_fulfill_unknown_error(self):
        """Test Course Entitlement Fulfillment with exception when posting to LMS."""

        self.mock_access_token_response()
        httpretty.register_uri(httpretty.POST, get_lms_entitlement_api_url() +
                               'entitlements/', status=408, body={}, content_type='application/json')
        logger_name = 'ecommerce.extensions.fulfillment.modules'

        line = self.order.lines.first()

        with LogCapture(logger_name) as l:
            CourseEntitlementFulfillmentModule().fulfill_product(self.order, list(self.order.lines.all()))
            self.assertEqual(LINE.FULFILLMENT_SERVER_ERROR, self.order.lines.all()[0].status)
            l.check(
                (logger_name, 'INFO', 'Attempting to fulfill "Course Entitlement" product types for order [{}]'.
                 format(self.order.number)),
                (logger_name, 'ERROR', 'Unable to fulfill line [{}] of order [{}]'.
                 format(line.id, self.order.number)),
                (logger_name, 'INFO', 'Finished fulfilling "Course Entitlement" product types for order [{}]'.
                 format(self.order.number))
            )

    def test_entitlement_module_fulfill_network_error(self):
        """Test Course Entitlement Fulfillment with exceptions(Timeout/ConnectionError) when posting to LMS."""

        logger_name = 'ecommerce.extensions.fulfillment.modules'

        line = self.order.lines.first()
        with mock.patch('edx_rest_api_client.client.EdxRestApiClient',
                        side_effect=ConnectionError):
            with LogCapture(logger_name) as l:
                CourseEntitlementFulfillmentModule().fulfill_product(self.order, list(self.order.lines.all()))
                self.assertEqual(LINE.FULFILLMENT_NETWORK_ERROR, self.order.lines.all()[0].status)
                l.check(
                    (logger_name, 'INFO', 'Attempting to fulfill "Course Entitlement" product types for order [{}]'.
                     format(self.order.number)),
                    (logger_name, 'ERROR', 'Unable to fulfill line [{}] of order [{}] due to a network problem'.
                     format(line.id, self.order.number)),
                    (logger_name, 'INFO', 'Finished fulfilling "Course Entitlement" product types for order [{}]'.
                     format(self.order.number))
                )

    def test_entitlement_module_fulfill_bad_attributes(self):
        """ Test the Entitlement Fulfillment Module fails when the product does not have proper attributes. """
        ProductAttribute.objects.get(product_class__name=COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME,
                                     code='UUID').delete()
        CourseEntitlementFulfillmentModule().fulfill_product(self.order, list(self.order.lines.all()))
        self.assertEqual(LINE.FULFILLMENT_CONFIGURATION_ERROR, self.order.lines.all()[0].status)
