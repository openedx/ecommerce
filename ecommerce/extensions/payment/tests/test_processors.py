# -*- coding: utf-8 -*-
"""Unit tests of payment processor implementations."""
import datetime
import json
import logging
from urlparse import urljoin
from uuid import UUID

import ddt
from django.conf import settings
from django.core.urlresolvers import reverse
from django.test.client import RequestFactory
import httpretty
import mock
from oscar.apps.payment.exceptions import TransactionDeclined, UserCancelled, GatewayError
from oscar.core.loading import get_model
from oscar.test import factories
import paypalrestsdk
from paypalrestsdk import Payment, Sale
from paypalrestsdk.resource import Resource
from testfixtures import LogCapture

from ecommerce.core.constants import ISO_8601_FORMAT
from ecommerce.core.tests import toggle_switch
from ecommerce.courses.models import Course
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.extensions.order.constants import PaymentEventTypeName
from ecommerce.extensions.payment.exceptions import (InvalidSignatureError, InvalidCybersourceDecision,
                                                     PartialAuthorizationError)
from ecommerce.extensions.payment.models import PaypalWebProfile
from ecommerce.extensions.payment.processors.invoice import InvoicePayment
from ecommerce.extensions.payment.processors.cybersource import Cybersource, suds_response_to_dict
from ecommerce.extensions.payment.processors.paypal import Paypal
from ecommerce.extensions.payment.tests.mixins import PaymentEventsMixin, CybersourceMixin, PaypalMixin
from ecommerce.extensions.refund.tests.mixins import RefundTestMixin
from ecommerce.tests.testcases import TestCase

PaymentEvent = get_model('order', 'PaymentEvent')
PaymentEventType = get_model('order', 'PaymentEventType')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')
Source = get_model('payment', 'Source')
SourceType = get_model('payment', 'SourceType')

log = logging.getLogger(__name__)


class PaymentProcessorTestCaseMixin(RefundTestMixin, CourseCatalogTestMixin, PaymentEventsMixin):
    """ Mixin for payment processor tests. """

    # Subclasses should set this value. It will be used to instantiate the processor in setUp.
    processor_class = None

    # This value is used to test the NAME attribute on the processor.
    processor_name = None

    CERTIFICATE_TYPE = 'test-certificate-type'

    def setUp(self):
        super(PaymentProcessorTestCaseMixin, self).setUp()

        self.course = Course.objects.create(id='a/b/c', name='Demo Course')
        self.product = self.course.create_or_update_seat(self.CERTIFICATE_TYPE, False, 20, self.partner)

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

    def test_issue_credit(self):
        """ Verify the payment processor responds appropriately to requests to issue credit. """
        raise NotImplementedError

    def test_issue_credit_error(self):
        """ Verify the payment processor responds appropriately if the payment gateway cannot issue a credit. """
        raise NotImplementedError


@ddt.ddt
class CybersourceTests(CybersourceMixin, PaymentProcessorTestCaseMixin, TestCase):
    """ Tests for CyberSource payment processor. """
    PI_DAY = datetime.datetime(2015, 3, 14, 9, 26, 53)
    UUID = u'UUID'

    processor_class = Cybersource
    processor_name = 'cybersource'

    def test_get_transaction_parameters(self):
        """ Verify the processor returns the appropriate parameters required to complete a transaction. """

        # Patch the datetime object so that we can validate the signed_date_time field
        with mock.patch.object(Cybersource, u'utcnow', return_value=self.PI_DAY):
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
            u'reference_number': self.basket.order_number,
            u'amount': unicode(self.basket.total_incl_tax),
            u'currency': self.basket.currency,
            u'consumer_id': self.basket.owner.username,
            u'override_custom_receipt_page': u'{}?orderNum={}'.format(self.processor.receipt_page_url,
                                                                      self.basket.order_number),
            u'override_custom_cancel_page': self.processor.cancel_page_url,
            u'merchant_defined_data1': self.course.id,
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
        get_single_seat = Cybersource.get_single_seat

        # finds the seat when it's the only product in the basket.
        self.assertEqual(get_single_seat(self.basket), self.product)

        # finds the first seat added, when there's more than one.
        basket = factories.create_basket(empty=True)
        other_seat = factories.ProductFactory(
            product_class=self.seat_product_class,
            stockrecords__price_currency='USD',
            stockrecords__partner__short_code='test',
        )
        basket.add_product(self.product)
        basket.add_product(other_seat)
        self.assertEqual(get_single_seat(basket), self.product)

        # finds the seat when there's a mixture of product classes.
        basket = factories.create_basket(empty=True)
        other_product = factories.ProductFactory(
            stockrecords__price_currency='USD',
            stockrecords__partner__short_code='test2',
        )
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

    @httpretty.activate
    def test_issue_credit(self):
        transaction_id = 'request-1234'
        refund = self.create_refund(self.processor_name)
        order = refund.order
        basket = order.basket
        amount = refund.total_credit_excl_tax
        currency = refund.currency
        source = order.sources.first()

        self.mock_cybersource_wsdl()

        self.assertEqual(source.amount_refunded, 0)
        self.assertFalse(order.payment_events.exists())

        cs_soap_mock = self.get_soap_mock(amount=amount, currency=currency, transaction_id=transaction_id,
                                          basket_id=basket.id)
        with mock.patch('suds.client.ServiceSelector', cs_soap_mock):
            self.processor.issue_credit(source, amount, currency)

        # Verify PaymentProcessorResponse created
        self.assert_processor_response_recorded(self.processor.NAME, transaction_id,
                                                suds_response_to_dict(cs_soap_mock().runTransaction()),
                                                basket)

        # Verify Source updated
        self.assertEqual(source.amount_refunded, amount)

        # Verify PaymentEvent created
        paid_type = PaymentEventType.objects.get(code=u'refunded')
        payment_event = order.payment_events.first()
        self.assert_valid_payment_event_fields(payment_event, amount, paid_type, self.processor.NAME, transaction_id)

    @httpretty.activate
    def test_issue_credit_error(self):
        transaction_id = 'request-1234'
        refund = self.create_refund(self.processor_name)
        order = refund.order
        basket = order.basket
        amount = refund.total_credit_excl_tax
        currency = refund.currency
        source = order.sources.first()

        self.mock_cybersource_wsdl()

        # Test for communication failure.
        with mock.patch('suds.client.ServiceSelector', mock.Mock(side_effect=Exception)):
            self.assertRaises(GatewayError, self.processor.issue_credit, source, amount, currency)
            self.assertEqual(source.amount_refunded, 0)

        # Test for declined transaction
        cs_soap_mock = self.get_soap_mock(amount=amount, currency=currency, transaction_id=transaction_id,
                                          basket_id=basket.id, decision='DECLINE')
        with mock.patch('suds.client.ServiceSelector', cs_soap_mock):
            self.assertRaises(GatewayError, self.processor.issue_credit, source, amount, currency)
            self.assert_processor_response_recorded(self.processor.NAME, transaction_id,
                                                    suds_response_to_dict(cs_soap_mock().runTransaction()),
                                                    basket)
            self.assertEqual(source.amount_refunded, 0)


@ddt.ddt
class PaypalTests(PaypalMixin, PaymentProcessorTestCaseMixin, TestCase):
    """Tests for the PayPal payment processor."""
    ERROR = {u'debug_id': u'foo'}

    processor_class = Paypal
    processor_name = u'paypal'

    def setUp(self):
        super(PaypalTests, self).setUp()

        # Dummy request from which an HTTP Host header can be extracted during
        # construction of absolute URLs
        self.request = RequestFactory().post('/')
        self.processor_response_log = (
            u"Failed to execute PayPal payment on attempt [{attempt_count}]. "
            u"PayPal's response was recorded in entry [{entry_id}]."
        )

    def _assert_transaction_parameters(self):
        """DRY helper for verifying transaction parameters."""
        expected = {
            u'payment_page_url': self.APPROVAL_URL,
        }
        actual = self.processor.get_transaction_parameters(self.basket, request=self.request)
        self.assertEqual(actual, expected)

    def _assert_payment_event_and_source(self, payer_info):
        """DRY helper for verifying a payment event and source."""
        source, payment_event = self.processor.handle_processor_response(self.RETURN_DATA, basket=self.basket)

        # Validate Source
        source_type = SourceType.objects.get(code=self.processor.NAME)
        reference = self.PAYMENT_ID
        label = 'PayPal ({})'.format(payer_info['email']) if 'email' in payer_info else 'PayPal Account'
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

        last_request_body = json.loads(httpretty.last_request().body)
        expected = urljoin(settings.ECOMMERCE_URL_ROOT, reverse('paypal_execute'))
        self.assertEqual(last_request_body['redirect_urls']['return_url'], expected)

    @httpretty.activate
    @mock.patch('ecommerce.extensions.payment.processors.paypal.paypalrestsdk.Payment')
    @ddt.data(None, Paypal.DEFAULT_PROFILE_NAME, "some-other-name")
    def test_web_profiles(self, enabled_profile_name, mock_payment):
        """
        Verify that the payment creation payload references a web profile when one is enabled with the expected name.
        """
        mock_payment_instance = mock.Mock()
        mock_payment_instance.to_dict.return_value = {}
        mock_payment_instance.links = [mock.Mock(rel='approval_url', href='dummy')]
        mock_payment.return_value = mock_payment_instance
        if enabled_profile_name is not None:
            PaypalWebProfile.objects.create(name=enabled_profile_name, id="test-profile-id")

        self.processor.get_transaction_parameters(self.basket, request=self.request)
        payment_creation_payload = mock_payment.call_args[0][0]
        if enabled_profile_name == Paypal.DEFAULT_PROFILE_NAME:
            self.assertEqual(payment_creation_payload['experience_profile_id'], "test-profile-id")
        else:
            self.assertNotIn('experience_profile_id', payment_creation_payload)

    @httpretty.activate
    @mock.patch.object(Paypal, '_get_error', mock.Mock(return_value=ERROR))
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
        for payer_info in (PaypalMixin.PAYER_INFO, {"shipping_address": None}):
            httpretty.reset()
            log.info("Testing payer_info with email set to: %s", payer_info.get("email"))
            self.mock_oauth2_response()
            self.mock_payment_creation_response(self.basket, find=True)
            response = self.mock_payment_execution_response(self.basket, payer_info=payer_info)

            self._assert_payment_event_and_source(payer_info)
            self.assert_processor_response_recorded(self.processor.NAME, self.PAYMENT_ID, response, basket=self.basket)

    @httpretty.activate
    @mock.patch.object(Paypal, '_get_error', mock.Mock(return_value=ERROR))
    def test_unexpected_payment_execution_state(self):
        """Verify that failure to execute a payment results in a GatewayError."""
        self.mock_oauth2_response()
        self.mock_payment_creation_response(self.basket, find=True)
        self.mock_payment_execution_response(self.basket)

        with mock.patch.object(paypalrestsdk.Payment, 'success', return_value=False):
            logger_name = 'ecommerce.extensions.payment.processors.paypal'
            with LogCapture(logger_name) as paypal_logger:
                self.assertRaises(GatewayError, self.processor.handle_processor_response, self.RETURN_DATA, self.basket)
                payment_processor_response = self.assert_processor_response_recorded(
                    self.processor.NAME,
                    self.ERROR['debug_id'],
                    self.ERROR,
                    basket=self.basket
                )

                paypal_logger.check(
                    (
                        logger_name, 'WARNING', self.processor_response_log.format(
                            attempt_count=1,
                            entry_id=payment_processor_response
                        )
                    ),
                    (
                        logger_name, 'ERROR',
                        u"Failed to execute PayPal payment [{payment_id}]. "
                        u"PayPal's response was recorded in entry [{entry_id}].".format(
                            payment_id=self.PAYMENT_ID,
                            entry_id=payment_processor_response
                        )
                    ),
                )

    @httpretty.activate
    @mock.patch.object(Paypal, '_get_error', mock.Mock(return_value=ERROR))
    def test_unexpected_payment_execution_with_retry_attempt(self):
        """Verify that, when the switch is active, failure to execute a payment
        results in one, or more, retry attempts. If all attempts fail, verify a
        GatewayError is raised.
        """
        toggle_switch('PAYPAL_RETRY_ATTEMPTS', True)
        self.mock_oauth2_response()
        self.mock_payment_creation_response(self.basket, find=True)
        self.mock_payment_execution_response(self.basket)

        with mock.patch.object(paypalrestsdk.Payment, 'success', return_value=False):
            logger_name = 'ecommerce.extensions.payment.processors.paypal'
            with LogCapture(logger_name) as paypal_logger:
                self.assertRaises(GatewayError, self.processor.handle_processor_response, self.RETURN_DATA, self.basket)

                # Each failure response is saved into db.
                payment_processor_responses = self.assert_processor_multiple_response_recorded()

                paypal_logger.check(
                    (
                        logger_name, 'WARNING', self.processor_response_log.format(
                            attempt_count=1,
                            entry_id=payment_processor_responses[0]
                        )
                    ),
                    (
                        logger_name, 'WARNING', self.processor_response_log.format(
                            attempt_count=2,
                            entry_id=payment_processor_responses[1]
                        )
                    ),
                    (
                        logger_name, 'ERROR',
                        u"Failed to execute PayPal payment [{payment_id}]. "
                        u"PayPal's response was recorded in entry [{entry_id}].".format(
                            payment_id=self.PAYMENT_ID,
                            entry_id=payment_processor_responses[1]
                        )
                    ),
                )

    def test_issue_credit(self):
        refund = self.create_refund(self.processor_name)
        order = refund.order
        basket = order.basket
        amount = refund.total_credit_excl_tax
        currency = refund.currency
        source = order.sources.first()

        transaction_id = 'PAY-REFUND-1'
        paypal_refund = paypalrestsdk.Refund({'id': transaction_id})

        payment = Payment(
            {'transactions': [Resource({'related_resources': [Resource({'sale': Sale({'id': 'PAY-SALE-1'})})]})]})
        with mock.patch.object(Payment, 'find', return_value=payment):
            with mock.patch.object(Sale, 'refund', return_value=paypal_refund):
                self.processor.issue_credit(source, amount, currency)

        # Verify PaymentProcessorResponse created
        self.assert_processor_response_recorded(self.processor.NAME, transaction_id, {'id': transaction_id}, basket)

        # Verify Source updated
        self.assertEqual(source.amount_refunded, amount)

        # Verify PaymentEvent created
        paid_type = PaymentEventType.objects.get(code=u'refunded')
        order = basket.order_set.first()
        payment_event = order.payment_events.first()
        self.assert_valid_payment_event_fields(payment_event, amount, paid_type, self.processor.NAME, transaction_id)

    def test_issue_credit_error(self):
        refund = self.create_refund(self.processor_name)
        order = refund.order
        basket = order.basket
        amount = refund.total_credit_excl_tax
        currency = refund.currency
        source = order.sources.first()

        transaction_id = 'PAY-REFUND-FAIL-1'
        expected_response = {'debug_id': transaction_id}
        paypal_refund = paypalrestsdk.Refund({'error': expected_response})

        payment = Payment(
            {'transactions': [Resource({'related_resources': [Resource({'sale': Sale({'id': 'PAY-SALE-1'})})]})]})

        # Test general exception
        with mock.patch.object(Payment, 'find', return_value=payment):
            with mock.patch.object(Sale, 'refund', side_effect=ValueError):
                self.assertRaises(GatewayError, self.processor.issue_credit, source, amount, currency)
                self.assertEqual(source.amount_refunded, 0)

        # Test error response
        with mock.patch.object(Payment, 'find', return_value=payment):
            with mock.patch.object(Sale, 'refund', return_value=paypal_refund):
                self.assertRaises(GatewayError, self.processor.issue_credit, source, amount, currency)

        # Verify PaymentProcessorResponse created
        self.assert_processor_response_recorded(self.processor.NAME, transaction_id, expected_response, basket)

        # Verify Source unchanged
        self.assertEqual(source.amount_refunded, 0)

    def assert_processor_multiple_response_recorded(self):
        """ Ensures a multiple PaymentProcessorResponse can store in db for the
        corresponding processor and response.
        """
        payment_processor_responses = PaymentProcessorResponse.objects.filter(
            processor_name=self.processor_name,
            transaction_id=self.ERROR['debug_id']
        )
        ids = []
        for payment_response in payment_processor_responses:
            self.assertEqual(payment_response.response, self.ERROR)
            self.assertEqual(payment_response.basket, self.basket)
            ids.append(payment_response.id)

        return ids


class InvoiceTests(TestCase):
    """ Tests for Invoice payment processor. """

    def setUp(self):
        super(InvoiceTests, self).setUp()
        self.processor_class = InvoicePayment
        self.processor_name = 'invoice'
        self.course = Course.objects.create(id='a/b/c', name='Demo Course')
        self.product = self.course.create_or_update_seat('verified', True, 50, self.partner)
        self.processor = self.processor_class()  # pylint: disable=not-callable
        self.basket = factories.create_basket(empty=True)
        self.basket.add_product(self.product)
        self.basket.owner = factories.UserFactory()
        self.basket.save()

    def test_handle_processor_response(self):
        """ Verify the processor creates the appropriate PaymentEvent and Source objects. """

        source, payment_event = self.processor_class().handle_processor_response({}, basket=self.basket)

        # Validate PaymentEvent
        self.assertEqual(payment_event.event_type.name, PaymentEventTypeName.PAID)

        # Validate PaymentSource
        self.assertEqual(source.source_type.name, self.processor.NAME)

    def test_transaction_parameters(self):
        """Test for transaction parameters"""
        params = self.processor_class().get_transaction_parameters(self.basket)
        self.assertIsNone(None, params)
