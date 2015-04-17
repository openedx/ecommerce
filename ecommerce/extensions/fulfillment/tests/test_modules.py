"""Tests of the Fulfillment API's fulfillment modules."""
import ddt
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from oscar.test.newfactories import UserFactory, BasketFactory
import mock
from nose.tools import raises
from oscar.test import factories
from requests import Response
from requests.exceptions import ConnectionError, Timeout
from rest_framework import status

from ecommerce.extensions.fulfillment.modules import EnrollmentFulfillmentModule
from ecommerce.extensions.fulfillment.status import LINE
from ecommerce.extensions.fulfillment.tests.mixins import FulfillmentTestMixin


User = get_user_model()


@ddt.ddt
@override_settings(EDX_API_KEY='foo')
class EnrollmentFulfillmentModuleTests(FulfillmentTestMixin, TestCase):
    """Test course seat fulfillment."""

    def setUp(self):
        user = UserFactory()
        self.product_class = factories.ProductClassFactory(
            name='Seat', requires_shipping=False, track_stock=False
        )

        self.course = factories.ProductFactory(
            structure='parent', upc='001', title='EdX DemoX Course', product_class=self.product_class
        )
        self.seat = factories.ProductFactory(
            structure='child',
            upc='002',
            title='Seat in EdX DemoX Course with Honor Certificate',
            product_class=None,
            parent=self.course
        )
        for stock_record in self.seat.stockrecords.all():
            stock_record.price_currency = 'USD'
            stock_record.save()

        basket = BasketFactory()
        basket.add_product(self.seat, 1)
        self.order = factories.create_order(number=1, basket=basket, user=user)

    def test_enrollment_module_support(self):
        """Test that we get the correct values back for supported product lines."""
        supported_lines = EnrollmentFulfillmentModule().get_supported_lines(self.order, list(self.order.lines.all()))
        self.assertEqual(1, len(supported_lines))

    @mock.patch('requests.post')
    def test_enrollment_module_fulfill(self, mock_post_request):
        """Happy path test to ensure we can properly fulfill enrollments."""
        fake_enrollment_api_response = Response()
        fake_enrollment_api_response.status_code = status.HTTP_200_OK
        mock_post_request.return_value = fake_enrollment_api_response

        self._create_attributes()

        # Attempt to enroll.
        EnrollmentFulfillmentModule().fulfill_product(self.order, list(self.order.lines.all()))
        self.assertEqual(LINE.COMPLETE, self.order.lines.all()[0].status)

    @override_settings(ENROLLMENT_API_URL='')
    def test_enrollment_module_not_configured(self):
        """Test that lines receive a configuration error status if fulfillment configuration is invalid."""
        EnrollmentFulfillmentModule().fulfill_product(self.order, list(self.order.lines.all()))
        self.assertEqual(LINE.FULFILLMENT_CONFIGURATION_ERROR, self.order.lines.all()[0].status)

    def test_enrollment_module_fulfill_bad_attributes(self):
        """Test that use of the Fulfillment Module fails when the product does not have attributes."""
        # Attempt to enroll without creating the product attributes.
        EnrollmentFulfillmentModule().fulfill_product(self.order, list(self.order.lines.all()))
        self.assertEqual(LINE.FULFILLMENT_CONFIGURATION_ERROR, self.order.lines.all()[0].status)

    @mock.patch('requests.post', mock.Mock(side_effect=ConnectionError))
    def test_enrollment_module_network_error(self):
        """Test that lines receive a network error status if a fulfillment request experiences a network error."""
        self._create_attributes()
        EnrollmentFulfillmentModule().fulfill_product(self.order, list(self.order.lines.all()))
        self.assertEqual(LINE.FULFILLMENT_NETWORK_ERROR, self.order.lines.all()[0].status)

    @mock.patch('requests.post', mock.Mock(side_effect=Timeout))
    def test_enrollment_module_request_timeout(self):
        """Test that lines receive a timeout error status if a fulfillment request times out."""
        self._create_attributes()
        EnrollmentFulfillmentModule().fulfill_product(self.order, list(self.order.lines.all()))
        self.assertEqual(LINE.FULFILLMENT_TIMEOUT_ERROR, self.order.lines.all()[0].status)

    @ddt.data(None, '{"message": "Oops!"}')
    def test_enrollment_module_server_error(self, response_content):
        """Test that lines receive a server-side error status if a server-side error occurs during fulfillment."""
        # NOTE: We are testing for cases where the response does and does NOT have data. The module should be able
        # to handle both cases.
        fake_error_response = Response()
        fake_error_response._content = response_content  # pylint: disable=protected-access
        fake_error_response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

        with mock.patch('requests.post', return_value=fake_error_response):
            self._create_attributes()

            # Attempt to enroll
            EnrollmentFulfillmentModule().fulfill_product(self.order, list(self.order.lines.all()))
            self.assertEqual(LINE.FULFILLMENT_SERVER_ERROR, self.order.lines.all()[0].status)

    @raises(NotImplementedError)
    def test_enrollment_module_revoke(self):
        """Test that use of this method due to "not implemented" error."""
        EnrollmentFulfillmentModule().revoke_product(self.order, list(self.order.lines.all()))

    def _create_attributes(self):
        """Create enrollment attributes and values for the Honor Seat in DemoX Course."""
        certificate_type = factories.ProductAttributeFactory(
            name='certificate_type', product_class=self.product_class, type="text"
        )
        certificate_type.save()

        course_key = factories.ProductAttributeFactory(
            name='course_key', product_class=self.product_class, type="text"
        )
        course_key.save()

        certificate_value = factories.ProductAttributeValueFactory(
            attribute=certificate_type, product=self.seat, value_text='honor'
        )
        certificate_value.save()

        key_value = factories.ProductAttributeValueFactory(
            attribute=course_key, product=self.seat, value_text='edX/DemoX/Demo_Course'
        )
        key_value.save()
