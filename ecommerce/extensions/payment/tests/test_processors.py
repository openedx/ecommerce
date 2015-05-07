# -*- coding: utf-8 -*-
"""Unit tests of payment processor implementations."""
from uuid import UUID
import datetime

import ddt
from django.conf import settings
from django.test import TestCase
from django.test.client import RequestFactory
import httpretty
import mock
from oscar.apps.payment.exceptions import TransactionDeclined, UserCancelled, GatewayError
from oscar.core.loading import get_model
from oscar.test import factories
import paypalrestsdk

from ecommerce.extensions.payment import processors
from ecommerce.extensions.payment.constants import ISO_8601_FORMAT
from ecommerce.extensions.payment.exceptions import (InvalidSignatureError, InvalidCybersourceDecision,
                                                     PartialAuthorizationError)
from ecommerce.extensions.payment.tests.mixins import PaymentEventsMixin, CybersourceMixin, PaypalMixin


PaymentEventType = get_model('order', 'PaymentEventType')
SourceType = get_model('payment', 'SourceType')


class PaymentProcessorTestCaseMixin(PaymentEventsMixin):
    """ Mixin for payment processor tests. """

    # Subclasses should set this value. It will be used to instantiate the processor in setUp.
    processor_class = None

    # This value is used to test the NAME attribute on the processor.
    processor_name = None

    COURSE_KEY = 'test-course-key'
    CERTIFICATE_TYPE = 'test-certificate-type'

    def setUp(self):
        super(PaymentProcessorTestCaseMixin, self).setUp()

        # certain logic and tests expect to find products with class 'seat' in
        # baskets, so that's done explicitly in this setup.
        self.product_class = factories.ProductClassFactory(slug='seat', requires_shipping=False, track_stock=False)
        factories.ProductAttributeFactory(code='course_key', product_class=self.product_class, type="text")
        factories.ProductAttributeFactory(code='certificate_type', product_class=self.product_class, type="text")

        self.product = factories.ProductFactory(product_class=self.product_class, stockrecords__price_currency='USD')
        self.product.attr.course_key = self.COURSE_KEY
        self.product.attr.certificate_type = self.CERTIFICATE_TYPE
        self.product.save()

        self.processor = self.processor_class()  # pylint: disable=not-callable
        self.basket = factories.create_basket(empty=True)
        self.basket.add_product(self.product)
        self.basket.owner = factories.UserFactory()
        self.basket.save()

    def test_configuration(self):
        """ Verifies configuration is read from settings. """
        self.assertDictEqual(self.processor.configuration, settings.PAYMENT_PROCESSOR_CONFIG[self.processor.NAME])

    def test_name(self):
        """Test that the name constant on the processor class is correct."""
        self.assertEqual(self.processor.NAME, self.processor_name)

    def test_get_transaction_parameters(self):
        """ Verify the processor returns the appropriate parameters required to complete a transaction. """
        raise NotImplementedError

    def test_handle_processor_response(self):
        """ Verify that the processor creates the appropriate PaymentEvent and Source objects. """
        raise NotImplementedError


@ddt.ddt
class CybersourceTests(CybersourceMixin, PaymentProcessorTestCaseMixin, TestCase):
    """ Tests for CyberSource payment processor. """
    PI_DAY = datetime.datetime(2015, 3, 14, 9, 26, 53)
    UUID = u'UUID'

    processor_class = processors.Cybersource
    processor_name = 'cybersource'

    def test_get_transaction_parameters(self):
        """ Verify the processor returns the appropriate parameters required to complete a transaction. """

        # Patch the datetime object so that we can validate the signed_date_time field
        with mock.patch.object(processors.datetime, u'datetime', mock.Mock(wraps=datetime.datetime)) as mocked_datetime:
            mocked_datetime.utcnow.return_value = self.PI_DAY
            actual = self.processor.get_transaction_parameters(self.basket)

        configuration = settings.PAYMENT_PROCESSOR_CONFIG[self.processor_name]
        access_key = configuration[u'access_key']
        profile_id = configuration[u'profile_id']

        expected = {
            u'access_key': access_key,
            u'profile_id': profile_id,
            u'signed_field_names': u'',
            u'unsigned_field_names': u'',
            u'signed_date_time': self.PI_DAY.strftime(ISO_8601_FORMAT),
            u'locale': settings.LANGUAGE_CODE,
            u'transaction_type': u'sale',
            u'reference_number': unicode(self.basket.id),
            u'amount': unicode(self.basket.total_incl_tax),
            u'currency': self.basket.currency,
            u'consumer_id': self.basket.owner.username,
            u'override_custom_receipt_page': u'{}?basket_id={}'.format(self.processor.receipt_page_url, self.basket.id),
            u'override_custom_cancel_page': self.processor.cancel_page_url,
            u'merchant_defined_data1': self.COURSE_KEY,
            u'merchant_defined_data2': self.CERTIFICATE_TYPE,
        }

        signed_field_names = expected.keys() + [u'transaction_uuid']
        expected[u'signed_field_names'] = u','.join(sorted(signed_field_names))

        # Copy the UUID value so that we can properly generate the signature. We will validate the UUID below.
        expected[u'transaction_uuid'] = actual[u'transaction_uuid']
        expected[u'signature'] = self.generate_signature(self.processor.secret_key, expected)
        self.assertDictContainsSubset(expected, actual)

        # If this raises an exception, the value is not a valid UUID4.
        UUID(actual[u'transaction_uuid'], version=4)

    def test_is_signature_valid(self):
        """ Verify that the is_signature_valid method properly validates the response's signature. """

        # Empty data should never be valid
        self.assertFalse(self.processor.is_signature_valid({}))

        # The method should return False for responses with invalid signatures.
        response = {
            u'signed_field_names': u'field_1,field_2,signed_field_names',
            u'field_2': u'abc',
            u'field_1': u'123',
            u'signature': u'abc123=='
        }
        self.assertFalse(self.processor.is_signature_valid(response))

        # The method should return True if the signature is valid.
        del response[u'signature']
        response[u'signature'] = self.generate_signature(self.processor.secret_key, response)
        self.assertTrue(self.processor.is_signature_valid(response))

    def test_handle_processor_response(self):
        """ Verify the processor creates the appropriate PaymentEvent and Source objects. """

        response = self.generate_notification(self.processor.secret_key, self.basket)
        reference = response[u'transaction_id']
        source, payment_event = self.processor.handle_processor_response(response, basket=self.basket)

        # Validate the Source
        source_type = SourceType.objects.get(code=self.processor.NAME)
        label = response[u'req_card_number']
        self.assert_basket_matches_source(
            self.basket,
            source,
            source_type,
            reference,
            label,
            card_type=self.DEFAULT_CARD_TYPE
        )

        # Validate PaymentEvent
        paid_type = PaymentEventType.objects.get(code=u'paid')
        amount = self.basket.total_incl_tax
        self.assert_valid_payment_event_fields(payment_event, amount, paid_type, self.processor.NAME, reference)

    def test_handle_processor_response_invalid_signature(self):
        """
        The handle_processor_response method should raise an InvalidSignatureError if the response's
        signature is not valid.
        """
        response = self.generate_notification(self.processor.secret_key, self.basket)
        response[u'signature'] = u'Tampered.'
        self.assertRaises(InvalidSignatureError, self.processor.handle_processor_response, response, basket=self.basket)

    @ddt.data(
        (u'CANCEL', UserCancelled),
        (u'DECLINE', TransactionDeclined),
        (u'ERROR', GatewayError),
        (u'huh?', InvalidCybersourceDecision))
    @ddt.unpack
    def test_handle_processor_response_not_accepted(self, decision, exception):
        """ The handle_processor_response method should raise an exception if payment was not accepted. """

        response = self.generate_notification(self.processor.secret_key, self.basket, decision=decision)
        self.assertRaises(exception, self.processor.handle_processor_response, response, basket=self.basket)

    def test_handle_processor_response_invalid_auth_amount(self):
        """
        The handle_processor_response method should raise PartialAuthorizationError if the authorized amount
        differs from the requested amount.
        """
        response = self.generate_notification(self.processor.secret_key, self.basket, auth_amount=u'0.00')
        self.assertRaises(PartialAuthorizationError, self.processor.handle_processor_response, response,
                          basket=self.basket)

    def test_get_single_seat(self):
        """
        The single-seat helper for cybersource reporting should correctly
        and return the first 'seat' product encountered in a basket.
        """
        get_single_seat = processors.Cybersource.get_single_seat

        # finds the seat when it's the only product in the basket.
        self.assertEqual(get_single_seat(self.basket), self.product)

        # finds the first seat added, when there's more than one.
        basket = factories.create_basket(empty=True)
        other_seat = factories.ProductFactory(product_class=self.product_class, stockrecords__price_currency='USD')
        basket.add_product(self.product)
        basket.add_product(other_seat)
        self.assertEqual(get_single_seat(basket), self.product)

        # finds the seat when there's a mixture of product classes.
        basket = factories.create_basket(empty=True)
        other_product = factories.ProductFactory(stockrecords__price_currency='USD')
        basket.add_product(other_product)
        basket.add_product(self.product)
        self.assertEqual(get_single_seat(basket), self.product)
        self.assertNotEqual(get_single_seat(basket), other_product)

        # returns None when there's no seats.
        basket = factories.create_basket(empty=True)
        basket.add_product(other_product)
        self.assertIsNone(get_single_seat(basket))

        # returns None for an empty basket.
        basket = factories.create_basket(empty=True)
        self.assertIsNone(get_single_seat(basket))


@ddt.ddt
class PaypalTests(PaypalMixin, PaymentProcessorTestCaseMixin, TestCase):
    """Tests for the PayPal payment processor."""
    ERROR = {u'debug_id': u'foo'}

    processor_class = processors.Paypal
    processor_name = u'paypal'

    def setUp(self):
        super(PaypalTests, self).setUp()

        # Dummy request from which an HTTP Host header can be extracted during
        # construction of absolute URLs
        self.request = RequestFactory().post('/')

    def _assert_transaction_parameters(self):
        """DRY helper for verifying transaction parameters."""
        expected = {
            u'payment_page_url': self.APPROVAL_URL,
        }
        actual = self.processor.get_transaction_parameters(self.basket, request=self.request)
        self.assertEqual(actual, expected)

    def _assert_payment_event_and_source(self):
        """DRY helper for verifying a payment event and source."""
        source, payment_event = self.processor.handle_processor_response(self.RETURN_DATA, basket=self.basket)

        # Validate Source
        source_type = SourceType.objects.get(code=self.processor.NAME)
        reference = self.PAYMENT_ID
        label = self.EMAIL
        self.assert_basket_matches_source(self.basket, source, source_type, reference, label)

        # Validate PaymentEvent
        paid_type = PaymentEventType.objects.get(code=u'paid')
        amount = self.basket.total_incl_tax
        self.assert_valid_payment_event_fields(payment_event, amount, paid_type, self.processor.NAME, reference)

    @httpretty.activate
    def test_get_transaction_parameters(self):
        """Verify the processor returns the appropriate parameters required to complete a transaction."""
        self.mock_oauth2_response()
        response = self.mock_payment_creation_response(self.basket)

        self._assert_transaction_parameters()
        self.assert_processor_response_recorded(self.processor.NAME, self.PAYMENT_ID, response, basket=self.basket)

    @httpretty.activate
    @mock.patch.object(processors.Paypal, '_get_error', mock.Mock(return_value=ERROR))
    def test_unexpected_payment_creation_state(self):
        """Verify that failure to create a payment results in a GatewayError."""
        self.mock_oauth2_response()
        self.mock_payment_creation_response(self.basket)

        with mock.patch.object(paypalrestsdk.Payment, 'success', return_value=False):
            self.assertRaises(
                GatewayError,
                self.processor.get_transaction_parameters,
                self.basket,
                request=self.request
            )
            self.assert_processor_response_recorded(
                self.processor.NAME,
                self.ERROR['debug_id'],
                self.ERROR,
                basket=self.basket
            )

    @httpretty.activate
    def test_approval_url_missing(self):
        """Verify that a missing approval URL results in a GatewayError."""
        self.mock_oauth2_response()
        response = self.mock_payment_creation_response(self.basket, approval_url=None)

        self.assertRaises(GatewayError, self.processor.get_transaction_parameters, self.basket, request=self.request)
        self.assert_processor_response_recorded(self.processor.NAME, self.PAYMENT_ID, response, basket=self.basket)

    @httpretty.activate
    def test_handle_processor_response(self):
        """Verify that the processor creates the appropriate PaymentEvent and Source objects."""
        self.mock_oauth2_response()
        self.mock_payment_creation_response(self.basket, find=True)
        response = self.mock_payment_execution_response(self.basket)

        self._assert_payment_event_and_source()
        self.assert_processor_response_recorded(self.processor.NAME, self.PAYMENT_ID, response, basket=self.basket)

    @httpretty.activate
    @mock.patch.object(processors.Paypal, '_get_error', mock.Mock(return_value=ERROR))
    def test_unexpected_payment_execution_state(self):
        """Verify that failure to execute a payment results in a GatewayError."""
        self.mock_oauth2_response()
        self.mock_payment_creation_response(self.basket, find=True)
        self.mock_payment_execution_response(self.basket)

        with mock.patch.object(paypalrestsdk.Payment, 'success', return_value=False):
            self.assertRaises(GatewayError, self.processor.handle_processor_response, self.RETURN_DATA, self.basket)
            self.assert_processor_response_recorded(
                self.processor.NAME,
                self.ERROR['debug_id'],
                self.ERROR,
                basket=self.basket
            )
