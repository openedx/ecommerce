# -*- coding: utf-8 -*-
"""Unit tests of payment processor implementations."""
import datetime
import json
from uuid import UUID

import ddt
from django.conf import settings
from django.test import TestCase
import mock
from oscar.apps.payment.exceptions import TransactionDeclined, UserCancelled, GatewayError
from oscar.core.loading import get_model
from oscar.test import factories

from ecommerce.extensions.payment import processors
from ecommerce.extensions.payment.constants import ISO_8601_FORMAT
from ecommerce.extensions.payment.exceptions import (InvalidSignatureError, InvalidCybersourceDecision,
                                                     PartialAuthorizationError)
from ecommerce.extensions.payment.tests.mixins import PaymentEventsMixin, CybersourceMixin


PaymentEventType = get_model('order', 'PaymentEventType')
SourceType = get_model('payment', 'SourceType')


class PaymentProcessorTestCaseMixin(PaymentEventsMixin):
    """ Mixin for payment processor tests. """

    # Subclasses should set this value. It will be used to instantiate the processor in setUp.
    processor_class = None

    # This value is used to test the NAME attribute on the processor.
    processor_name = None

    def setUp(self):
        super(PaymentProcessorTestCaseMixin, self).setUp()
        self.processor = self.processor_class()  # pylint: disable=not-callable
        self.basket = factories.create_basket()
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

    def test_is_signature_valid(self):
        """ Verify that the is_signature_valid method properly validates the response's signature. """
        raise NotImplementedError


@ddt.ddt
class CybersourceTests(CybersourceMixin, PaymentProcessorTestCaseMixin, TestCase):
    """ Tests for CyberSource payment processor. """
    UUID = u'UUID'
    PI_DAY = datetime.datetime(2015, 3, 14, 9, 26, 53)

    processor_class = processors.Cybersource
    processor_name = 'cybersource'

    def assert_valid_transaction_parameters(self, cancel_page_url=None, receipt_page_url=None, tracking_context=None):
        """ Validates the transaction parameters returned by get_transaction_parameters(). """

        # Patch the datetime object so that we can validate the signed_date_time field
        with mock.patch.object(processors.datetime, u'datetime', mock.Mock(wraps=datetime.datetime)) as mocked_datetime:
            mocked_datetime.utcnow.return_value = self.PI_DAY
            actual = self.processor.get_transaction_parameters(self.basket,
                                                               cancel_page_url=cancel_page_url,
                                                               receipt_page_url=receipt_page_url,
                                                               tracking_context=tracking_context)

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
        }

        if tracking_context is not None:
            expected[u'req_merchant_secure_data4'] = json.dumps({'tracking_context': tracking_context})

        cancel_page_url = cancel_page_url or self.processor.cancel_page_url
        if cancel_page_url:
            expected[u'override_custom_cancel_page'] = cancel_page_url

        if self.processor.receipt_page_url and not receipt_page_url:
            receipt_page_url = u'{}?basket_id={}'.format(self.processor.receipt_page_url, self.basket.id)

        if receipt_page_url:
            expected[u'override_custom_receipt_page'] = receipt_page_url

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

        expected_tracking_context = {'lms_user_id': 'test-user-id', 'lms_client_id': 'test-client-id'}
        response = self.generate_notification(self.processor.secret_key, self.basket,
                                              tracking_context=expected_tracking_context)
        reference = response[u'transaction_id']
        source, payment_event, actual_tracking_context = self.processor.handle_processor_response(response,
                                                                                                  basket=self.basket)

        # Validate the Source
        source_type = SourceType.objects.get(code=self.processor.NAME)
        label = response[u'req_card_number']
        self.assert_basket_matches_source(self.basket, source, source_type, reference, label)

        # Validate PaymentEvent
        paid_type = PaymentEventType.objects.get(code=u'paid')
        amount = self.basket.total_incl_tax
        self.assert_valid_payment_event_fields(payment_event, amount, paid_type, self.processor.NAME, reference)

        # Validate tracking_context
        self.assertEqual(expected_tracking_context, actual_tracking_context)

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

    @mock.patch('ecommerce.extensions.payment.processors.json.loads', side_effect=Exception("Kaboom!"))
    @mock.patch('ecommerce.extensions.payment.processors.logger.warning')
    def test_handle_processor_response_tracking_error(self, mock_warning, mock_loads):
        """ Ensure that failure to parse tracking context from the Cybersource callback causes a warning to be
            logged, but does not otherwise disrupt the transaction.
        """
        response = self.generate_notification(self.processor.secret_key, self.basket, tracking_context={'foo': 'bar'})
        self.processor.handle_processor_response(response, basket=self.basket)
        self.assertTrue(mock_loads.called)
        self.assertTrue(
            mock_warning.called_with("Failed to parse tracking context from cybersource response, skipping.")
        )

    def test_get_transaction_parameters(self):
        """ Verify the processor returns the appropriate parameters required to complete a transaction. """

        # Test with settings overrides
        self.processor.receipt_page_url = u'http://example.com/receipt/'
        self.processor.cancel_page_url = u'http://example.com/cancel/'
        self.assert_valid_transaction_parameters()

        # Test with receipt page override
        self.assert_valid_transaction_parameters(receipt_page_url=u'http://example.com/receipt/')

        # Test with cancel page override
        self.assert_valid_transaction_parameters(cancel_page_url=u'http://example.com/cancel/')

        # Test with both overrides
        self.assert_valid_transaction_parameters(cancel_page_url=u'http://example.com/cancel/',
                                                 receipt_page_url=u'http://example.com/receipt/')

        # Test without overrides
        self.processor.receipt_page_url = None
        self.processor.cancel_page_url = None
        self.assert_valid_transaction_parameters()

        # Test with tracking context
        self.assert_valid_transaction_parameters(
            tracking_context={'lms_user_id': 'test-user-id', 'lms_client_id': 'test-client-id'}
        )
