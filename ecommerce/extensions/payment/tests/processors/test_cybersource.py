# -*- coding: utf-8 -*-
"""Unit tests of Cybersource payment processor implementation."""
from __future__ import unicode_literals

import copy
from uuid import UUID

import ddt
import httpretty
import mock
from django.conf import settings
from django.test import override_settings
from freezegun import freeze_time
from oscar.apps.payment.exceptions import UserCancelled, TransactionDeclined, GatewayError

from ecommerce.extensions.payment.exceptions import (
    InvalidSignatureError, InvalidCybersourceDecision, PartialAuthorizationError, PCIViolation,
    ProcessorMisconfiguredError
)
from ecommerce.extensions.payment.processors.cybersource import Cybersource, suds_response_to_dict
from ecommerce.extensions.payment.tests.mixins import CybersourceMixin
from ecommerce.extensions.payment.tests.processors.mixins import PaymentProcessorTestCaseMixin
from ecommerce.tests.testcases import TestCase


@ddt.ddt
class CybersourceTests(CybersourceMixin, PaymentProcessorTestCaseMixin, TestCase):
    """ Tests for CyberSource payment processor. """
    processor_class = Cybersource
    processor_name = 'cybersource'

    def setUp(self):
        super(CybersourceTests, self).setUp()
        self.toggle_ecommerce_receipt_page(True)
        self.basket.site = self.site

    @freeze_time('2016-01-01')
    def assert_correct_transaction_parameters(self, include_level_2_3_details=True, **kwargs):
        """ Verifies the processor returns the correct parameters required to complete a transaction.

         Arguments
            include_level_23_details (bool): Determines if Level 2/3 details should be included in the parameters.
        """
        # NOTE (CCB): Instantiate a new processor object to ensure we reload any overridden settings.
        actual = self.processor_class(self.site).get_transaction_parameters(self.basket, **kwargs)

        expected = self.get_expected_transaction_parameters(
            self.basket,
            actual['transaction_uuid'],
            include_level_2_3_details,
            processor=self.processor,
            **kwargs
        )
        self.assertDictContainsSubset(expected, actual)

        # Verify the extra data is included
        extra_parameters = kwargs.get('extra_parameters', {})
        self.assertDictContainsSubset(extra_parameters, actual)

        # If this raises an exception, the value is not a valid UUID4.
        UUID(actual['transaction_uuid'], version=4)

    def test_get_transaction_parameters(self):
        """ Verify the processor returns the appropriate parameters required to complete a transaction. """
        # NOTE (CCB): Make a deepcopy of the settings so that we can modify them without affecting the real settings.
        # This is a bit simpler than using modify_copy(), which would does not support nested dictionaries.
        payment_processor_config = copy.deepcopy(settings.PAYMENT_PROCESSOR_CONFIG)
        payment_processor_config['edx'][self.processor_name]['send_level_2_3_details'] = False

        with override_settings(PAYMENT_PROCESSOR_CONFIG=payment_processor_config):
            self.assert_correct_transaction_parameters(include_level_2_3_details=False)

    def test_get_transaction_parameters_with_level2_3_details(self):
        """ Verify the processor returns parameters including Level 2/3 details. """
        self.assert_correct_transaction_parameters()

    def test_get_transaction_parameters_with_extra_parameters(self):
        """ Verify the method supports adding additional unsigned parameters. """
        extra_parameters = {'payment_method': 'card'}
        self.assert_correct_transaction_parameters(extra_parameters=extra_parameters)

    @ddt.data('card_type', 'card_number', 'card_expiry_date', 'card_cvn')
    def test_get_transaction_parameters_with_unpermitted_parameters(self, field):
        """ Verify the method raises an error if un-permitted parameters are passed to the method. """
        with self.assertRaises(PCIViolation):
            extra_parameters = {field: 'This value is irrelevant.'}
            self.processor.get_transaction_parameters(self.basket, extra_parameters=extra_parameters)

    @ddt.data('sop_access_key', 'sop_payment_page_url', 'sop_profile_id', 'sop_secret_key')
    def test_get_transaction_parameters_with_missing_sop_configuration(self, key):
        """ Verify attempts to get transaction parameters for Silent Order POST fail if the appropriate settings
        are not configured.
        """
        # NOTE (CCB): Make a deepcopy of the settings so that we can modify them without affecting the real settings.
        # This is a bit simpler than using modify_copy(), which would does not support nested dictionaries.
        payment_processor_config = copy.deepcopy(settings.PAYMENT_PROCESSOR_CONFIG)

        # Remove the key/field from settings
        del payment_processor_config['edx'][self.processor_name][key]

        with override_settings(PAYMENT_PROCESSOR_CONFIG=payment_processor_config):
            with self.assertRaises(ProcessorMisconfiguredError):
                # NOTE (CCB): Instantiate a new processor object to ensure we reload any overridden settings.
                self.processor_class(self.site).get_transaction_parameters(self.basket, use_client_side_checkout=True)

    def test_is_signature_valid(self):
        """ Verify that the is_signature_valid method properly validates the response's signature. """

        # Empty data should never be valid
        self.assertFalse(self.processor.is_signature_valid({}))

        # The method should return False for responses with invalid signatures.
        response = {
            'req_profile_id': self.processor.profile_id,
            'signed_field_names': 'field_1,field_2,signed_field_names',
            'field_2': 'abc',
            'field_1': '123',
            'signature': 'abc123=='
        }
        self.assertFalse(self.processor.is_signature_valid(response))

        # The method should return True if the signature is valid.
        response['signature'] = self.generate_signature(self.processor.secret_key, response)
        self.assertTrue(self.processor.is_signature_valid(response))

        # The method should return True if the signature is valid for a Silent Order POST response.
        response['req_profile_id'] = self.processor.sop_profile_id
        response['signature'] = self.generate_signature(self.processor.sop_secret_key, response)
        self.assertTrue(self.processor.is_signature_valid(response))

        # The method should return False if the response has no req_profile_id field.
        del response['req_profile_id']
        self.assertFalse(self.processor.is_signature_valid(response))

    def test_handle_processor_response(self):
        """ Verify the processor creates the appropriate PaymentEvent and Source objects. """

        response = self.generate_notification(self.basket)
        handled_response = self.processor.handle_processor_response(response, basket=self.basket)
        self.assertEqual(handled_response.currency, self.basket.currency)
        self.assertEqual(handled_response.total, self.basket.total_incl_tax)
        self.assertEqual(handled_response.transaction_id, response['transaction_id'])
        self.assertEqual(handled_response.card_number, response['req_card_number'])
        self.assertEqual(handled_response.card_type, self.DEFAULT_CARD_TYPE)

    def test_handle_processor_response_invalid_signature(self):
        """
        The handle_processor_response method should raise an InvalidSignatureError if the response's
        signature is not valid.
        """
        response = self.generate_notification(self.basket)
        response['signature'] = 'Tampered.'
        self.assertRaises(InvalidSignatureError, self.processor.handle_processor_response, response, basket=self.basket)

    @ddt.data(
        ('CANCEL', UserCancelled),
        ('DECLINE', TransactionDeclined),
        ('ERROR', GatewayError),
        ('huh?', InvalidCybersourceDecision))
    @ddt.unpack
    def test_handle_processor_response_not_accepted(self, decision, exception):
        """ The handle_processor_response method should raise an exception if payment was not accepted. """

        response = self.generate_notification(self.basket, decision=decision)
        self.assertRaises(exception, self.processor.handle_processor_response, response, basket=self.basket)

    def test_handle_processor_response_invalid_auth_amount(self):
        """
        The handle_processor_response method should raise PartialAuthorizationError if the authorized amount
        differs from the requested amount.
        """
        response = self.generate_notification(self.basket, auth_amount='0.00')
        self.assertRaises(PartialAuthorizationError, self.processor.handle_processor_response, response,
                          basket=self.basket)

    @httpretty.activate
    def test_issue_credit(self):
        """
        Tests issue_credit operation
        """
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
            actual = self.processor.issue_credit(order, source.reference, amount, currency)
            self.assertEqual(actual, transaction_id)

        # Verify PaymentProcessorResponse created
        self.assert_processor_response_recorded(self.processor.NAME, transaction_id,
                                                suds_response_to_dict(cs_soap_mock().runTransaction()),
                                                basket)

    @httpretty.activate
    def test_issue_credit_error(self):
        """
        Tests that issue_credit errors in case of communication error or declined transaction
        """
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
            self.assertRaises(GatewayError, self.processor.issue_credit, order, source.reference, amount, currency)
            self.assertEqual(source.amount_refunded, 0)

        # Test for declined transaction
        cs_soap_mock = self.get_soap_mock(amount=amount, currency=currency, transaction_id=transaction_id,
                                          basket_id=basket.id, decision='DECLINE')
        with mock.patch('suds.client.ServiceSelector', cs_soap_mock):
            self.assertRaises(GatewayError, self.processor.issue_credit, order, source.reference, amount, currency)
            self.assert_processor_response_recorded(self.processor.NAME, transaction_id,
                                                    suds_response_to_dict(cs_soap_mock().runTransaction()),
                                                    basket)
            self.assertEqual(source.amount_refunded, 0)

    def test_client_side_payment_url(self):
        """ Verify the property returns the Silent Order POST URL. """
        processor_config = settings.PAYMENT_PROCESSOR_CONFIG[self.partner.name.lower()][self.processor.NAME.lower()]
        expected = processor_config['sop_payment_page_url']
        self.assertEqual(self.processor.client_side_payment_url, expected)
