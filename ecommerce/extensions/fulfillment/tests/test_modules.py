"""Tests of the Fulfillment API's fulfillment modules."""


import datetime
import json
import uuid
from decimal import Decimal
from urllib.parse import urlencode

import ddt
import mock
import responses
from django.conf import settings
from django.test import override_settings
from oscar.core.loading import get_class, get_model
from oscar.test import factories
from requests.exceptions import ConnectionError as ReqConnectionError
from requests.exceptions import Timeout
from testfixtures import LogCapture
from waffle.testutils import override_switch

from ecommerce.core.constants import (
    COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME,
    DONATIONS_FROM_CHECKOUT_TESTS_PRODUCT_TYPE_NAME,
    ENROLLMENT_CODE_PRODUCT_CLASS_NAME,
    HUBSPOT_FORMS_INTEGRATION_ENABLE,
    ISO_8601_FORMAT,
    SEAT_PRODUCT_CLASS_NAME
)
from ecommerce.core.url_utils import get_lms_enrollment_api_url, get_lms_entitlement_api_url
from ecommerce.coupons.tests.mixins import CouponMixin
from ecommerce.courses.constants import CertificateType
from ecommerce.courses.models import Course
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.courses.utils import mode_for_product
from ecommerce.enterprise.conditions import EnterpriseCustomerCondition
from ecommerce.enterprise.tests.mixins import EnterpriseDiscountTestMixin
from ecommerce.entitlements.utils import create_or_update_course_entitlement
from ecommerce.extensions.basket.constants import PURCHASER_BEHALF_ATTRIBUTE
from ecommerce.extensions.basket.utils import basket_add_organization_attribute
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.extensions.fulfillment.modules import (
    CouponFulfillmentModule,
    CourseEntitlementFulfillmentModule,
    DonationsFromCheckoutTestFulfillmentModule,
    EnrollmentCodeFulfillmentModule,
    EnrollmentFulfillmentModule,
    ExecutiveEducation2UFulfillmentModule
)
from ecommerce.extensions.fulfillment.status import LINE
from ecommerce.extensions.fulfillment.tests.mixins import FulfillmentTestMixin
from ecommerce.extensions.payment.models import EnterpriseContractMetadata
from ecommerce.extensions.test.factories import (
    EnterpriseOfferFactory,
    EnterprisePercentageDiscountBenefitFactory,
    create_order
)
from ecommerce.extensions.voucher.models import OrderLineVouchers
from ecommerce.extensions.voucher.utils import create_vouchers
from ecommerce.programs.tests.mixins import ProgramTestMixin
from ecommerce.tests.factories import UserFactory
from ecommerce.tests.testcases import TestCase

JSON = 'application/json'
LOGGER_NAME = 'ecommerce.extensions.analytics.utils'

Applicator = get_class('offer.applicator', 'Applicator')
Benefit = get_model('offer', 'Benefit')
Catalog = get_model('catalogue', 'Catalog')
ConditionalOffer = get_model('offer', 'ConditionalOffer')
OrderDiscount = get_model('order', 'OrderDiscount')
Option = get_model('catalogue', 'Option')
Product = get_model('catalogue', 'Product')
ProductAttribute = get_model('catalogue', 'ProductAttribute')
ProductClass = get_model('catalogue', 'ProductClass')
Range = get_model('offer', 'Range')
StockRecord = get_model('partner', 'StockRecord')
Voucher = get_model('voucher', 'Voucher')


@ddt.ddt
@override_settings(EDX_API_KEY='foo')
class EnrollmentFulfillmentModuleTests(
        EnterpriseDiscountTestMixin,
        ProgramTestMixin,
        DiscoveryTestMixin,
        FulfillmentTestMixin,
        TestCase
):
    """Test course seat fulfillment."""

    course_id = 'edX/DemoX/Demo_Course'
    certificate_type = 'test-certificate-type'
    provider = None

    def setUp(self):
        super(EnrollmentFulfillmentModuleTests, self).setUp()

        self.user = UserFactory()
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
        coupon = self.create_coupon_product()
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
        Applicator().apply_offers(self.order.basket, vouchers[0].offers.all())

    def test_enrollment_module_support(self):
        """Test that we get the correct values back for supported product lines."""
        supported_lines = EnrollmentFulfillmentModule().get_supported_lines(list(self.order.lines.all()))
        self.assertEqual(1, len(supported_lines))

    @responses.activate
    def test_enrollment_module_fulfill(self):
        """Happy path test to ensure we can properly fulfill enrollments."""
        responses.add(responses.POST, get_lms_enrollment_api_url(), status=200, json={}, content_type=JSON)
        # Attempt to enroll.
        with LogCapture(LOGGER_NAME) as logger:
            EnrollmentFulfillmentModule().fulfill_product(self.order, list(self.order.lines.all()))

            line = self.order.lines.get()
            logger.check_present(
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

        last_request = responses.calls[-1].request
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
                },
                {
                    'namespace': 'order',
                    'name': 'date_placed',
                    'value': self.order.date_placed.strftime(ISO_8601_FORMAT)
                }
            ]
        }

        expected_headers = {
            'X-Edx-Ga-Client-Id': self.user.tracking_context['ga_client_id'],
            'X-Forwarded-For': self.user.tracking_context['lms_ip'],
        }

        self.assertDictContainsSubset(expected_headers, actual_headers)
        self.assertEqual(expected_body, actual_body)

    @responses.activate
    def test_enrollment_module_fulfill_order_with_discount_no_voucher(self):
        """
        Test that components of the Fulfillment Module which trigger on the presence of a voucher do
        not cause failures in cases where a discount does not have a voucher included
        (such as with a Conditional Offer)
        """
        responses.add(responses.POST, get_lms_enrollment_api_url(), status=200, body='{}', content_type=JSON)
        self.create_seat_and_order(certificate_type='credit', provider='MIT')
        self.order.discounts.create()
        __, lines = EnrollmentFulfillmentModule().fulfill_product(self.order, list(self.order.lines.all()))
        # No exceptions should be raised and the order should be fulfilled
        self.assertEqual(lines[0].status, 'Complete')

    @responses.activate
    def test_enrollment_module_fulfill_order_enterprise_discount_calculation(self):
        """
        Verify an orderline is updated with calculated enterprise discount data
        if a product is fulfilled with an enterprise offer for an enterprise
        customer and that enterprise offer has `enterprise_contract_metadata`
        associated with it.
        """
        responses.add(responses.POST, get_lms_enrollment_api_url(), status=200, body='{}', content_type=JSON)
        self.create_seat_and_order(certificate_type='credit', provider='MIT')

        self.create_order_offer_discount(
            self.order,
            enterprise_contract_metadata=EnterpriseContractMetadata.objects.create(
                discount_type=EnterpriseContractMetadata.FIXED,
                discount_value=Decimal('200.00'),
                amount_paid=Decimal('500.00')
            )
        )
        basket_strategy = self.order.basket.strategy
        self.order.refresh_from_db()
        # restore lost basket strategy after call to refresh_from_db
        self.order.basket.strategy = basket_strategy

        with mock.patch.object(Range, 'contains_product') as mock_contains:
            mock_contains.return_value = True
            with mock.patch.object(EnterpriseCustomerCondition, 'is_satisfied') as mock_satisfied:
                mock_satisfied.return_value = True
                with mock.patch(
                        "ecommerce.extensions.fulfillment.modules.get_or_create_enterprise_customer_user"
                ) as mock_get_or_create_enterprise_customer_user:
                    mock_get_or_create_enterprise_customer_user.return_value = mock.Mock()
                    Applicator().apply_offers(self.order.basket, [self.discount_offer])
                    __, lines = EnrollmentFulfillmentModule().fulfill_product(self.order, list(self.order.lines.all()))

        # No exceptions should be raised and the order should be fulfilled
        self.assertEqual(lines[0].status, 'Complete')
        self.assertIsInstance(lines[0].effective_contract_discount_percentage, Decimal)
        self.assertIsInstance(lines[0].effective_contract_discounted_price, Decimal)

    @responses.activate
    def test_enrollment_module_fulfill_order_no_enterprise_discount_calculation(self):
        """
        Verify an orderline is NOT updated with calculated enterprise discount data
        if a product is fulfilled with an enterprise offer for an enterprise
        customer and that enterprise offer has NO `enterprise_contract_metadata`
        associated with it.
        """
        responses.add(responses.POST, get_lms_enrollment_api_url(), status=200, body='{}', content_type=JSON)
        self.create_seat_and_order(certificate_type='credit', provider='MIT')

        # Creating order discount without EnterpriseContractMetadata object.
        self.create_order_offer_discount(self.order)

        basket_strategy = self.order.basket.strategy
        self.order.refresh_from_db()
        # restore lost basket strategy after call to refresh_from_db
        self.order.basket.strategy = basket_strategy

        with mock.patch.object(Range, 'contains_product') as mock_contains:
            mock_contains.return_value = True
            with mock.patch.object(EnterpriseCustomerCondition, 'is_satisfied') as mock_satisfied:
                mock_satisfied.return_value = True
                Applicator().apply_offers(self.order.basket, [self.discount_offer])
            __, lines = EnrollmentFulfillmentModule().fulfill_product(self.order, list(self.order.lines.all()))

        # No exceptions should be raised and the order should be fulfilled
        self.assertEqual(lines[0].status, 'Complete')
        assert lines[0].effective_contract_discount_percentage is None
        assert lines[0].effective_contract_discounted_price is None

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

    @mock.patch('requests.post', mock.Mock(side_effect=ReqConnectionError))
    def test_enrollment_module_network_error(self):
        """Test that lines receive a network error status if a fulfillment request experiences a network error."""
        EnrollmentFulfillmentModule().fulfill_product(self.order, list(self.order.lines.all()))
        self.assertEqual(LINE.FULFILLMENT_NETWORK_ERROR, self.order.lines.all()[0].status)

    @mock.patch('requests.post', mock.Mock(side_effect=Timeout))
    def test_enrollment_module_request_timeout(self):
        """Test that lines receive a timeout error status if a fulfillment request times out."""
        EnrollmentFulfillmentModule().fulfill_product(self.order, list(self.order.lines.all()))
        self.assertEqual(LINE.FULFILLMENT_TIMEOUT_ERROR, self.order.lines.all()[0].status)

    @responses.activate
    @ddt.data(None, '{"message": "Oops!"}')
    def test_enrollment_module_server_error(self, body):
        """Test that lines receive a server-side error status if a server-side error occurs during fulfillment."""
        # NOTE: We are testing for cases where the response does and does NOT have data. The module should be able
        # to handle both cases.
        responses.add(responses.POST, get_lms_enrollment_api_url(), status=500, body=body, content_type=JSON)
        EnrollmentFulfillmentModule().fulfill_product(self.order, list(self.order.lines.all()))
        self.assertEqual(LINE.FULFILLMENT_SERVER_ERROR, self.order.lines.all()[0].status)

    @responses.activate
    def test_revoke_product(self):
        """ The method should call the Enrollment API to un-enroll the student, and return True. """
        responses.add(responses.POST, get_lms_enrollment_api_url(), status=200, json={}, content_type=JSON)
        line = self.order.lines.first()

        with LogCapture(LOGGER_NAME) as logger:
            self.assertTrue(EnrollmentFulfillmentModule().revoke_line(line))

            logger.check_present(
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

        last_request = responses.calls[-1].request
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

    @responses.activate
    def test_revoke_product_expected_error(self):
        """
        If the Enrollment API responds with an expected error, the method should log that revocation was
        bypassed, and return True.
        """
        message = 'Enrollment mode mismatch: active mode=x, requested mode=y. Won\'t deactivate.'
        body = '{{"message": "{}"}}'.format(message)
        responses.add(responses.POST, get_lms_enrollment_api_url(), status=400, body=body, content_type=JSON)

        line = self.order.lines.first()
        logger_name = 'ecommerce.extensions.fulfillment.modules'
        with LogCapture(logger_name) as logger:
            self.assertTrue(EnrollmentFulfillmentModule().revoke_line(line))
            logger.check_present(
                (logger_name, 'INFO', 'Attempting to revoke fulfillment of Line [{}]...'.format(line.id)),
                (logger_name, 'INFO', 'Skipping revocation for line [%d]: %s' % (line.id, message))
            )

    @responses.activate
    def test_revoke_product_unexpected_error(self):
        """ If the Enrollment API responds with a non-200 status, the method should log an error and return False. """
        message = 'Meh.'
        body = '{{"message": "{}"}}'.format(message)
        responses.add(responses.POST, get_lms_enrollment_api_url(), status=500, body=body, content_type=JSON)

        line = self.order.lines.first()
        logger_name = 'ecommerce.extensions.fulfillment.modules'
        with LogCapture(logger_name) as logger:
            self.assertFalse(EnrollmentFulfillmentModule().revoke_line(line))
            logger.check_present(
                (logger_name, 'INFO', 'Attempting to revoke fulfillment of Line [{}]...'.format(line.id)),
                (logger_name, 'ERROR', 'Failed to revoke fulfillment of Line [%d]: %s' % (line.id, message))
            )

    @responses.activate
    def test_revoke_product_unknown_exception(self):
        """
        If an exception is raised while contacting the Enrollment API, the method should log an error and return False.
        """

        def request_callback(_method, _uri, _headers):
            raise Timeout

        responses.add(responses.POST, get_lms_enrollment_api_url(), body=request_callback)
        line = self.order.lines.first()
        logger_name = 'ecommerce.extensions.fulfillment.modules'

        with LogCapture(logger_name) as logger:
            self.assertFalse(EnrollmentFulfillmentModule().revoke_line(line))
            logger.check_present(
                (logger_name, 'INFO', 'Attempting to revoke fulfillment of Line [{}]...'.format(line.id)),
                (logger_name, 'ERROR', 'Failed to revoke fulfillment of Line [{}].'.format(line.id))
            )

    @responses.activate
    def test_credit_enrollment_module_fulfill(self):
        """Happy path test to ensure we can properly fulfill enrollments."""
        # Create the credit certificate type and order for the credit certificate type.
        self.create_seat_and_order(certificate_type='credit', provider='MIT')
        responses.add(responses.POST, get_lms_enrollment_api_url(), status=200, json={}, content_type=JSON)

        # Attempt to enroll.
        with LogCapture(LOGGER_NAME) as logger:
            EnrollmentFulfillmentModule().fulfill_product(self.order, list(self.order.lines.all()))

            line = self.order.lines.get()
            logger.check_present(
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

        actual = json.loads(responses.calls[-1].request.body)
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
                    'namespace': 'order',
                    'name': 'date_placed',
                    'value': self.order.date_placed.strftime(ISO_8601_FORMAT)
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
            EnrollmentFulfillmentModule()._post_to_enrollment_api(data=data, user=self.user, usage='test enrollment')
        except ReqConnectionError as exp:
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

    @responses.activate
    def test_voucher_usage_with_program(self):
        """
        Test that using a voucher with a program basket results in a fulfilled order.
        """
        responses.add(responses.POST, get_lms_enrollment_api_url(), status=200, body='{}', content_type=JSON)
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
        user = UserFactory()
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
        user = UserFactory()
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

    def create_order_with_billing_address(self):
        """ Creates an order object with a bit of extra information for HubSpot unit tests"""
        enrollment_code = Product.objects.get(product_class__name=ENROLLMENT_CODE_PRODUCT_CLASS_NAME)
        user = UserFactory()
        basket = factories.BasketFactory(owner=user, site=self.site)
        basket.add_product(enrollment_code, self.QUANTITY)

        # add organization and purchaser attributes manually to the basket for testing purposes
        basket_data = {
            'organization': 'Dummy Business Client',
            PURCHASER_BEHALF_ATTRIBUTE: 'True'
        }
        basket_add_organization_attribute(basket, basket_data)

        # add some additional data the billing address to exercise some of the code paths in the unit we are testing
        billing_address = factories.BillingAddressFactory()
        billing_address.line2 = 'Suite 321'
        billing_address.line4 = "City"
        billing_address.state = "State"
        billing_address.country.name = "United States of America"

        # create new order adding in the additional billing address info
        return create_order(number=2, basket=basket, user=user, billing_address=billing_address)

    def add_required_attributes_to_basket(self, order, purchased_by_org):
        """ Utility method that will setup Basket with attributes needed for unit tests """
        # add organization and purchaser attributes manually to the basket for testing purposes
        basket_data = {
            'organization': 'Dummy Business Client',
            PURCHASER_BEHALF_ATTRIBUTE: '{}'.format(purchased_by_org)
        }
        basket_add_organization_attribute(order.basket, basket_data)

    def set_hubspot_settings(self):
        # set the HubSpot specific settings with values that make it look close to a real world configuration
        settings.HUBSPOT_FORMS_API_URI = "https://forms.hubspot.com/uploads/form/v2/"
        settings.HUBSPOT_PORTAL_ID = "0"
        settings.HUBSPOT_SALES_LEAD_FORM_GUID = "00000000-1111-2222-3333-4444444444444444"

    def format_hubspot_request_url(self):
        return "{}{}/{}?&".format(
            settings.HUBSPOT_FORMS_API_URI,
            settings.HUBSPOT_PORTAL_ID,
            settings.HUBSPOT_SALES_LEAD_FORM_GUID)

    def setUp(self):
        super(EnrollmentCodeFulfillmentModuleTests, self).setUp()
        course = CourseFactory(partner=self.partner)
        course.create_or_update_seat('verified', True, 50, create_enrollment_code=True)
        enrollment_code = Product.objects.get(product_class__name=ENROLLMENT_CODE_PRODUCT_CLASS_NAME)
        user = UserFactory()
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

    def test_get_fulfillment_data(self):
        """ Test for gathering data to send to HubSpot """
        order = self.create_order_with_billing_address()

        # extract some of the course info we need to build our "expected" string for comparisons later
        product = order.lines.first().product
        course = Course.objects.get(id=product.attr.course_key)

        course_name_data = urlencode({
            'ecommerce_course_name': course.name
        })

        course_id_data = urlencode({
            'ecommerce_course_id': course.id
        })

        customer_email_data = urlencode({
            'email': order.basket.owner.email
        })

        expected_request_entries = [
            "firstname=John",
            "lastname=Doe",
            "company=Dummy+Business+Client",
            course_name_data,
            course_id_data,
            "deal_value=250.00",
            "address=Streetname%2C+Suite+321",
            "bulk_purchase_quantity=5",
            "city=City",
            "country=United+States",
            "state=State",
            customer_email_data,
        ]
        generated_request_body = EnrollmentCodeFulfillmentModule().get_order_fulfillment_data_for_hubspot(order)
        self.assertCountEqual(expected_request_entries, generated_request_body.split('&'))

    def test_determine_if_enterprise_purchase_expect_true(self):
        """ Test for being able to retrieve 'purchased_behalf_of' attribute from Basket and the checkbox is checked. """
        self.add_required_attributes_to_basket(self.order, True)
        purchased_by_organization = EnrollmentCodeFulfillmentModule().determine_if_enterprise_purchase(self.order)
        self.assertEqual(True, purchased_by_organization)

    def test_determine_if_enterprise_purchase_expect_false(self):
        """ Test for being able to retrieve 'purchased_behalf_of' attribute value from Basket and the checkbox is
        not checked. """
        self.add_required_attributes_to_basket(self.order, False)
        purchased_by_organization = EnrollmentCodeFulfillmentModule().determine_if_enterprise_purchase(self.order)
        self.assertEqual(False, purchased_by_organization)

    def test_determine_if_enterprise_purchase_no_organization(self):
        """ Test for ensuring we send back a usable value if 'purchased_behalf_of' attribute is missing from Basket
        for some reason. """
        purchased_by_organization = EnrollmentCodeFulfillmentModule().determine_if_enterprise_purchase(self.order)
        self.assertEqual(False, purchased_by_organization)

    @responses.activate
    def test_send_to_hubspot_happy_path(self):
        """ Test for constructing and sending the HubSpot request. Verifies expected logs are appearing. """
        order = self.create_order_with_billing_address()

        self.set_hubspot_settings()
        hubspot_url = self.format_hubspot_request_url()
        responses.add(
            responses.POST,
            hubspot_url,
            content_type='application/x-www-form-urlencoded',
            status=204
        )

        logger_name = "ecommerce.extensions.fulfillment.modules"
        with LogCapture(logger_name) as logger:
            response = EnrollmentCodeFulfillmentModule().send_fulfillment_data_to_hubspot(order)
            # verify we built the uri correctly
            self.assertEqual(response.url, hubspot_url)
            # verify that the expected logs were generated
            logger.check_present(
                (
                    logger_name,
                    'INFO',
                    'Gathering fulfillment data for submission to HubSpot for order [{}]'.format(order.number)
                ),
                (
                    logger_name,
                    'INFO',
                    'Sending data to HubSpot for order [{}]'.format(order.number)
                ),
                (
                    logger_name,
                    'DEBUG',
                    'HubSpot response: 204'
                )
            )

    @mock.patch('requests.post', mock.Mock(side_effect=Timeout))
    def test_send_to_hubspot_timeout(self):
        """ Test to simulate a timeout occurring when sending data to HubSpot. Verifies expected logs appear. """
        order = self.create_order_with_billing_address()

        logger_name = "ecommerce.extensions.fulfillment.modules"
        with LogCapture(logger_name) as logger:
            EnrollmentCodeFulfillmentModule().send_fulfillment_data_to_hubspot(order)
            # verify that the expected logs were generated
            logger.check_present(
                (
                    logger_name,
                    'ERROR',
                    'Timeout occurred attempting to send data to HubSpot for order [{}]'.format(order.number)
                )
            )

    @mock.patch('requests.post', mock.Mock(side_effect=ReqConnectionError))
    def test_send_to_hubspot_error(self):
        """ Test to simulate some other error occurring when sending data to HubSpot. Verifies expected logs appear. """
        order = self.create_order_with_billing_address()

        logger_name = "ecommerce.extensions.fulfillment.modules"
        with LogCapture(logger_name) as logger:
            EnrollmentCodeFulfillmentModule().send_fulfillment_data_to_hubspot(order)
            # verify that the expected logs were generated
            logger.check_present(
                (
                    logger_name,
                    'ERROR',
                    'Error occurred attempting to send data to HubSpot for order [{}]'.format(order.number)
                )
            )

    @responses.activate
    @override_switch(HUBSPOT_FORMS_INTEGRATION_ENABLE, active=True)
    def test_fulfill_product_hubspot_waffle_switch_enabled(self):
        """ Test that verifies if the HubSpot feature is enabled and the order contains the right information we
            will try and transmit this data to HubSpot.
        """
        order = self.create_order_with_billing_address()
        self.add_required_attributes_to_basket(order, True)

        self.set_hubspot_settings()
        hubspot_url = self.format_hubspot_request_url()
        responses.add(
            responses.POST,
            hubspot_url,
            content_type='application/x-www-form-urlencoded',
            status=204
        )

        logger_name = "ecommerce.extensions.fulfillment.modules"
        with LogCapture(logger_name) as logger:
            lines = self.order.lines.all()
            EnrollmentCodeFulfillmentModule().fulfill_product(order, lines)
            logger.check_present(
                (
                    logger_name,
                    'INFO',
                    'Attempting to fulfill \'Enrollment Code\' product types for order [{}]'.format(order.number)
                ),
                (
                    logger_name,
                    'INFO',
                    'Gathering fulfillment data for submission to HubSpot for order [{}]'.format(order.number)
                ),
                (
                    logger_name,
                    'INFO',
                    'Sending data to HubSpot for order [{}]'.format(order.number)
                ),
                (
                    logger_name,
                    'DEBUG',
                    'HubSpot response: 204'
                ),
                (
                    logger_name,
                    'INFO',
                    'Finished fulfilling \'Enrollment code\' product types for order [{}]'.format(order.number)
                )
            )

    @override_switch(HUBSPOT_FORMS_INTEGRATION_ENABLE, active=False)
    def test_fulfill_product_hubspot_waffle_switch_disabled(self):
        """ Test that verifies if the HubSpot feature is disabled but the order contains the right information we do not
        transmit this data to HubSpot
        """
        order = self.create_order_with_billing_address()
        self.add_required_attributes_to_basket(order, True)

        # HubSpot feature flag is disabled and we should _not_ try to send the order data to HubSpot. Verify logs look
        # as we would expect.
        logger_name = "ecommerce.extensions.fulfillment.modules"
        with LogCapture(logger_name) as logger:
            lines = self.order.lines.all()
            EnrollmentCodeFulfillmentModule().fulfill_product(order, lines)
            logger.check_present(
                (
                    logger_name,
                    'INFO',
                    'Attempting to fulfill \'Enrollment Code\' product types for order [{}]'.format(order.number)
                ),
                (
                    logger_name,
                    'INFO',
                    'Finished fulfilling \'Enrollment code\' product types for order [{}]'.format(order.number)
                )
            )


@ddt.ddt
class EntitlementFulfillmentModuleTests(FulfillmentTestMixin, EnterpriseDiscountTestMixin, TestCase):
    """ Test Course Entitlement Fulfillment """

    def setUp(self):
        super(EntitlementFulfillmentModuleTests, self).setUp()
        self.user = UserFactory()
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

    def test_entitlement_supports_line_exec_edu_2u_product(self):
        """ Test that support_line returns False Executive Education (2U) products. """
        exec_ed_2u_course_entitlement = create_or_update_course_entitlement(
            CertificateType.PAID_EXECUTIVE_EDUCATION,
            100,
            self.partner,
            '111-222-333-444',
            'Executive Education (2U) Course Entitlement'
        )

        basket = factories.BasketFactory(owner=self.user, site=self.site)
        basket.add_product(exec_ed_2u_course_entitlement, 1)
        order = create_order(number=2, basket=basket, user=self.user)

        unsupported_line = order.lines.first()
        supports_line = CourseEntitlementFulfillmentModule().supports_line(unsupported_line)
        self.assertFalse(supports_line)

    def test_get_entitlement_supported_lines(self):
        """ Test that Course Entitlement products lines are returned. """
        lines = self.order.lines.all()
        supported_lines = CourseEntitlementFulfillmentModule().get_supported_lines(lines)
        self.assertListEqual(supported_lines, list(lines))

    @responses.activate
    @ddt.unpack
    @ddt.data(
        # Test with voucher order discount
        {
            'amount_paid': Decimal('40'),
            'discount_value': Decimal('30'),
            'discount_type': EnterpriseContractMetadata.PERCENTAGE,
            'create_order_discount_callback': 'create_order_voucher_discount',
            'expected_effective_contract_discount_percentage': Decimal('0.3'),
            'expected_effective_contract_discounted_price': Decimal('70.0000'),
        },
        # Test with offer order discount
        {
            'amount_paid': Decimal('100'),
            'discount_value': Decimal('100'),
            'discount_type': EnterpriseContractMetadata.FIXED,
            'create_order_discount_callback': 'create_order_offer_discount',
            'expected_effective_contract_discount_percentage': Decimal('0.5'),
            'expected_effective_contract_discounted_price': Decimal('50.0000'),
        }
    )
    def test_entitlement_module_fulfill(
            self,
            amount_paid,
            discount_value,
            discount_type,
            create_order_discount_callback,
            expected_effective_contract_discount_percentage,
            expected_effective_contract_discounted_price
    ):
        """ Test to ensure we can properly fulfill course entitlements with order's voucher discount """
        self.mock_access_token_response()
        responses.add(
            responses.POST,
            get_lms_entitlement_api_url() + 'entitlements/',
            status=200, json=self.return_data,
            content_type='application/json'
        )
        getattr(self, create_order_discount_callback)(
            self.order,
            enterprise_contract_metadata=EnterpriseContractMetadata.objects.create(
                discount_type=discount_type,
                discount_value=discount_value,
                amount_paid=amount_paid
            )
        )
        # Attempt to fulfill entitlement.
        with LogCapture(LOGGER_NAME) as logger:
            with mock.patch(
                    "ecommerce.extensions.fulfillment.modules.get_or_create_enterprise_customer_user"
            ) as mock_get_or_create_enterprise_customer_user:
                mock_get_or_create_enterprise_customer_user.return_value = mock.Mock()
                CourseEntitlementFulfillmentModule().fulfill_product(self.order, list(self.order.lines.all()))

                line = self.order.lines.get()
                logger.check_present(
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
                # after updating the fields, they have expected values.
                self.assertEqual(
                    line.effective_contract_discount_percentage,
                    expected_effective_contract_discount_percentage
                )
                self.assertEqual(
                    line.effective_contract_discounted_price,
                    expected_effective_contract_discounted_price
                )

    @responses.activate
    def test_entitlement_module_revoke(self):
        """ Test to revoke a Course Entitlement. """
        self.mock_access_token_response()
        responses.add(
            responses.POST,
            get_lms_entitlement_api_url() + 'entitlements/',
            status=200,
            json=self.return_data,
            content_type='application/json'
        )

        responses.add(
            responses.DELETE,
            get_lms_entitlement_api_url() + 'entitlements/111-222-333/',
            status=200,
            content_type='application/json'
        )

        line = self.order.lines.first()

        # Fulfill order first to ensure we have all the line attributes set
        CourseEntitlementFulfillmentModule().fulfill_product(self.order, list(self.order.lines.all()))

        with LogCapture(LOGGER_NAME) as logger:
            self.assertTrue(CourseEntitlementFulfillmentModule().revoke_line(line))

            logger.check_present(
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

    @responses.activate
    def test_entitlement_module_revoke_error(self):
        """ Test to handle an error when revoking a Course Entitlement. """
        self.mock_access_token_response()

        responses.add(
            responses.DELETE,
            get_lms_entitlement_api_url() + 'entitlements/111-222-333/',
            status=500,
            body={},
            content_type='application/json'
        )

        line = self.order.lines.first()

        self.assertFalse(CourseEntitlementFulfillmentModule().revoke_line(line))

    @responses.activate
    def test_entitlement_module_fulfill_unknown_error(self):
        """Test Course Entitlement Fulfillment with exception when posting to LMS."""

        self.mock_access_token_response()
        responses.add(
            responses.POST,
            get_lms_entitlement_api_url() + 'entitlements/',
            status=408,
            body={},
            content_type='application/json'
        )
        logger_name = 'ecommerce.extensions.fulfillment.modules'

        line = self.order.lines.first()

        with LogCapture(logger_name) as logger:
            CourseEntitlementFulfillmentModule().fulfill_product(self.order, list(self.order.lines.all()))
            self.assertEqual(LINE.FULFILLMENT_SERVER_ERROR, self.order.lines.all()[0].status)
            logger.check_present(
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
        with mock.patch('edx_rest_api_client.client.OAuthAPIClient',
                        side_effect=ReqConnectionError):
            with LogCapture(logger_name) as logger:
                CourseEntitlementFulfillmentModule().fulfill_product(self.order, list(self.order.lines.all()))
                self.assertEqual(LINE.FULFILLMENT_NETWORK_ERROR, self.order.lines.all()[0].status)
                logger.check_present(
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


@ddt.ddt
class ExecutiveEducation2UFulfillmentModuleTests(
    FulfillmentTestMixin,
    EnterpriseDiscountTestMixin,
    TestCase
):
    def setUp(self):
        super().setUp()
        self.user = UserFactory()

        self.exec_ed_2u_course_entitlement = create_or_update_course_entitlement(
            CertificateType.PAID_EXECUTIVE_EDUCATION,
            100,
            self.partner,
            '111-222-333-444',
            'Executive Education (2U) Course Entitlement'
        )
        self.exec_ed_2u_course_entitlement_2 = create_or_update_course_entitlement(
            CertificateType.PAID_EXECUTIVE_EDUCATION,
            100,
            self.partner,
            '222-333-444-555',
            'Executive Education (2U) Course Entitlement 2'
        )

        self.non_exec_ed_2u_course_entitlement = create_or_update_course_entitlement(
            CertificateType.VERIFIED,
            100,
            self.partner,
            '333-444-555-666',
            'Regular Course Entitlement'
        )

        basket = factories.BasketFactory(owner=self.user, site=self.site)
        basket.add_product(self.exec_ed_2u_course_entitlement, 1)
        basket.add_product(self.exec_ed_2u_course_entitlement_2, 1)
        basket.add_product(self.non_exec_ed_2u_course_entitlement, 1)
        self.order = create_order(number=1, basket=basket, user=self.user)

        # Create enterprise offer for order
        offer = EnterpriseOfferFactory(
            partner=self.partner,
            benefit=EnterprisePercentageDiscountBenefitFactory(value=100)
        )
        factories.OrderDiscountFactory(
            order=self.order,
            offer_id=offer.id,
            amount=100
        )
        order_lines = self.order.lines.all()
        self.exec_ed_2u_entitlement_line = order_lines[0]
        self.exec_ed_2u_entitlement_line_2 = order_lines[1]
        self.non_exec_ed_2u_entitlement_line = order_lines[2]

        self.exec_ed_2u_entitlement_line.product.attr.variant_id = 'variant_id'
        self.exec_ed_2u_entitlement_line_2.product.attr.variant_id = 'variant_id-2'

        self.fulfillment_details = json.dumps({
            'address': {
                'address_line1': '10 Lovely Street',
                'city': 'Herndon',
                'postal_code': '35005',
                'state': 'California',
                'state_code': 'state_code',
                'country': 'country',
                'country_code': 'country_code',
            },
            'user_details': {
                'first_name': 'John',
                'last_name': 'Smith',
                'email': 'johnsmith@example.com',
                'date_of_birth': '2000-01-01',
                'mobile_phone': '+12015551234',
            },
            'terms_accepted_at': '2022-07-25T10:29:56Z',
            'data_share_consent': True
        })

        self.mock_settings = {
            'GET_SMARTER_OAUTH2_PROVIDER_URL': 'https://provider-url.com',
            'GET_SMARTER_OAUTH2_KEY': 'key',
            'GET_SMARTER_OAUTH2_SECRET': 'secret',
            'GET_SMARTER_API_URL': 'https://api-url.com',
        }

    def test_supports_line(self):
        self.assertTrue(
            ExecutiveEducation2UFulfillmentModule().supports_line(self.exec_ed_2u_entitlement_line)
        )
        self.assertFalse(
            ExecutiveEducation2UFulfillmentModule().supports_line(self.non_exec_ed_2u_entitlement_line)
        )

    def test_get_supported_lines(self):
        supported_lines = ExecutiveEducation2UFulfillmentModule().get_supported_lines(self.order.lines.all())
        self.assertEqual(len(supported_lines), 2)
        self.assertEqual(supported_lines[0], self.exec_ed_2u_entitlement_line)
        self.assertEqual(supported_lines[1], self.exec_ed_2u_entitlement_line_2)

    @mock.patch('ecommerce.extensions.fulfillment.modules.logger.exception')
    def test_fulfill_product_no_fulfillment_details(self, mock_logger):
        self.order.notes.all().delete()
        self.assertEqual(self.exec_ed_2u_entitlement_line.status, LINE.OPEN)
        ExecutiveEducation2UFulfillmentModule().fulfill_product(
            self.exec_ed_2u_entitlement_line.order,
            [self.exec_ed_2u_entitlement_line]
        )
        self.assertEqual(self.exec_ed_2u_entitlement_line.status, LINE.FULFILLMENT_SERVER_ERROR)
        mock_logger.assert_called_with(
            'Unable to fulfill order [%s] due to missing or malformed fulfillment details.',
            self.exec_ed_2u_entitlement_line.order.number
        )

    @mock.patch('ecommerce.extensions.fulfillment.modules.logger.exception')
    def test_fulfill_product_maformed_fulfillment_details(self, mock_logger):
        self.order.notes.create(message='', note_type='Fulfillment Details')
        self.assertEqual(self.exec_ed_2u_entitlement_line.status, LINE.OPEN)
        ExecutiveEducation2UFulfillmentModule().fulfill_product(
            self.exec_ed_2u_entitlement_line.order,
            [self.exec_ed_2u_entitlement_line]
        )
        self.assertEqual(self.exec_ed_2u_entitlement_line.status, LINE.FULFILLMENT_SERVER_ERROR)
        mock_logger.assert_called_with(
            'Unable to fulfill order [%s] due to missing or malformed fulfillment details.',
            self.exec_ed_2u_entitlement_line.order.number
        )

    @mock.patch('ecommerce.extensions.fulfillment.modules.create_enterprise_customer_user_consent')
    @mock.patch('ecommerce.extensions.fulfillment.modules.get_course_info_from_catalog')
    @mock.patch('ecommerce.extensions.fulfillment.modules.GetSmarterEnterpriseApiClient')
    def test_fulfill_product_success(
        self,
        mock_geag_client,
        mock_get_course_info_from_catalog,
        mock_create_enterprise_customer_user_consent
    ):
        with self.settings(**self.mock_settings):
            mock_create_enterprise_allocation = mock.MagicMock()
            mock_geag_client.return_value = mock.MagicMock(
                create_enterprise_allocation=mock_create_enterprise_allocation
            )
            mock_get_course_info_from_catalog.return_value = {
                'key': 'test_course_key1'
            }
            self.order.notes.create(message=self.fulfillment_details, note_type='Fulfillment Details')
            ExecutiveEducation2UFulfillmentModule().fulfill_product(
                self.order,
                [self.exec_ed_2u_entitlement_line, self.exec_ed_2u_entitlement_line_2]
            )
            self.assertEqual(mock_create_enterprise_allocation.call_count, 2)
            self.assertEqual(mock_create_enterprise_customer_user_consent.call_count, 2)
            self.assertEqual(self.exec_ed_2u_entitlement_line.status, LINE.COMPLETE)
            self.assertEqual(self.exec_ed_2u_entitlement_line_2.status, LINE.COMPLETE)
            self.assertFalse(self.order.notes.exists())

    @mock.patch('ecommerce.extensions.fulfillment.modules.create_enterprise_customer_user_consent')
    @mock.patch('ecommerce.extensions.fulfillment.modules.get_course_info_from_catalog')
    @mock.patch('ecommerce.extensions.fulfillment.modules.GetSmarterEnterpriseApiClient')
    def test_fulfill_product_error(
        self,
        mock_geag_client,
        mock_get_course_info_from_catalog,
        mock_create_enterprise_customer_user_consent
    ):
        with self.settings(**self.mock_settings):
            mock_create_enterprise_allocation = mock.MagicMock()
            mock_create_enterprise_allocation.side_effect = [None, Exception("Uh oh.")]
            mock_geag_client.return_value = mock.MagicMock(
                create_enterprise_allocation=mock_create_enterprise_allocation
            )
            mock_get_course_info_from_catalog.return_value = {
                'key': 'test_course_key1'
            }
            self.order.notes.create(message=self.fulfillment_details, note_type='Fulfillment Details')
            ExecutiveEducation2UFulfillmentModule().fulfill_product(
                self.order,
                [self.exec_ed_2u_entitlement_line, self.exec_ed_2u_entitlement_line_2]
            )
            self.assertEqual(mock_create_enterprise_allocation.call_count, 2)
            self.assertEqual(mock_create_enterprise_customer_user_consent.call_count, 2)
            self.assertEqual(self.exec_ed_2u_entitlement_line.status, LINE.COMPLETE)
            self.assertEqual(self.exec_ed_2u_entitlement_line_2.status, LINE.FULFILLMENT_SERVER_ERROR)
            self.assertTrue(self.order.notes.exists())

    def test_revoke_line(self):
        line = self.order.lines.first()
        with self.assertRaises(NotImplementedError):
            CouponFulfillmentModule().revoke_line(line)
