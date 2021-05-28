# -*- coding: utf-8 -*-
"""Unit tests of Cybersource payment processor implementation."""


import copy
import json
from decimal import Decimal
from unittest import SkipTest
from uuid import UUID

import ddt
import mock
import requests
import responses
from CyberSource.api_client import ApiClient
from django.conf import settings
from django.test import override_settings
from django.urls import reverse
from freezegun import freeze_time
from oscar.apps.payment.exceptions import GatewayError, TransactionDeclined, UserCancelled
from oscar.core.loading import get_model
from oscar.test import factories

from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.basket.tests.test_utils import TEST_BUNDLE_ID
from ecommerce.extensions.order.models import Order
from ecommerce.extensions.payment.exceptions import (
    ExcessivePaymentForOrderError,
    InvalidCybersourceDecision,
    InvalidSignatureError,
    PartialAuthorizationError,
    PCIViolation,
    ProcessorMisconfiguredError,
    RedundantPaymentNotificationError
)
from ecommerce.extensions.payment.models import PaymentProcessorResponse
from ecommerce.extensions.payment.processors.cybersource import (
    Cybersource,
    CybersourceREST,
    Decision,
    UnhandledCybersourceResponse
)
from ecommerce.extensions.payment.tests.mixins import CybersourceMixin, CyberSourceRESTAPIMixin
from ecommerce.extensions.payment.tests.processors.mixins import PaymentProcessorTestCaseMixin
from ecommerce.extensions.test.factories import create_basket
from ecommerce.tests.factories import UserFactory
from ecommerce.tests.testcases import TestCase

BasketAttribute = get_model('basket', 'BasketAttribute')
BasketAttributeType = get_model('basket', 'BasketAttributeType')


@ddt.ddt
class CybersourceTests(CybersourceMixin, PaymentProcessorTestCaseMixin, TestCase):
    """ Tests for CyberSource payment processor. """
    processor_class = Cybersource
    processor_name = 'cybersource'

    def assert_processor_response_recorded(self, processor_name, transaction_id, response, basket=None):
        """ Ensures a PaymentProcessorResponse exists for the corresponding processor and response. """
        ppr = PaymentProcessorResponse.objects.filter(
            processor_name=processor_name,
            transaction_id=transaction_id
        ).latest('created')

        # The response we have for CyberSource is XML. Rather than parse it, we simply check for a single key/value.
        # If that key/value is present it is reasonably safe to assume the others are present.
        expected = {
            'requestID': transaction_id,
        }
        self.assertDictContainsSubset(expected, ppr.response)
        self.assertEqual(ppr.basket, basket)

        return ppr.id

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

    def test_init_without_config(self):
        partner_short_code = self.partner.short_code

        payment_processor_config = copy.deepcopy(settings.PAYMENT_PROCESSOR_CONFIG)
        for key in ('sop_access_key', 'sop_payment_page_url', 'sop_profile_id', 'sop_secret_key', 'access_key',
                    'payment_page_url', 'profile_id', 'secret_key'):
            del payment_processor_config[partner_short_code][self.processor_name][key]

        with override_settings(PAYMENT_PROCESSOR_CONFIG=payment_processor_config):
            with self.assertRaisesMessage(
                    AssertionError,
                    'CyberSource processor must be configured for Silent Order POST and/or Secure Acceptance'):
                self.processor_class(self.site)

    def test_get_transaction_parameters(self):
        """ Verify the processor returns the appropriate parameters required to complete a transaction. """
        # NOTE (CCB): Make a deepcopy of the settings so that we can modify them without affecting the real settings.
        # This is a bit simpler than using modify_copy(), which would does not support nested dictionaries.
        payment_processor_config = copy.deepcopy(settings.PAYMENT_PROCESSOR_CONFIG)
        payment_processor_config['edx'][self.processor_name]['send_level_2_3_details'] = False

        with override_settings(PAYMENT_PROCESSOR_CONFIG=payment_processor_config):
            self.assert_correct_transaction_parameters(include_level_2_3_details=False)

    def test_get_transaction_parameters_with_program(self):
        """ Verify the processor returns parameters including Level 2/3 details. """
        bundle_id = TEST_BUNDLE_ID
        BasketAttribute.objects.update_or_create(
            basket=self.basket,
            attribute_type=BasketAttributeType.objects.get(name='bundle_identifier'),
            value_text=bundle_id
        )
        self.assert_correct_transaction_parameters(
            extra_parameters={
                'merchant_defined_data1': 'program,{}'.format(bundle_id),
                'merchant_defined_data2': 'course,a/b/c,audit'
            }
        )

    def test_get_transaction_parameters_with_level2_3_details(self):
        """ Verify the processor returns parameters including Level 2/3 details. """
        self.assert_correct_transaction_parameters(
            extra_parameters={
                'merchant_defined_data2': 'course,a/b/c,audit'
            }
        )

    def test_get_transaction_parameters_with_extra_parameters(self):
        """ Verify the method supports adding additional unsigned parameters. """
        extra_parameters = {
            'payment_method': 'card',
            'merchant_defined_data2': 'course,a/b/c,audit'
        }
        self.assert_correct_transaction_parameters(extra_parameters=extra_parameters)

    def test_get_transaction_parameters_with_quoted_product_title(self):
        """ Verify quotes are removed from item name """
        course = CourseFactory(id='a/b/c/d', name='Course with "quotes"')
        product = course.create_or_update_seat(self.CERTIFICATE_TYPE, False, 20)

        basket = create_basket(owner=UserFactory(), site=self.site, empty=True)
        basket.add_product(product)

        response = self.processor.get_transaction_parameters(basket)
        self.assertEqual(response['item_0_name'], 'Seat in Course with quotes with test-certificate-type certificate')

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
        handled_response = self.processor.handle_processor_response(
            self.processor.normalize_processor_response(response),
            basket=self.basket
        )
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
        self.assertRaises(
            InvalidSignatureError,
            self.processor.handle_processor_response,
            self.processor.normalize_processor_response(response),
            basket=self.basket
        )

    @ddt.data(
        ('CANCEL', UserCancelled),
        ('DECLINE', TransactionDeclined),
        ('ERROR', GatewayError),
        ('huh?', InvalidCybersourceDecision))
    @ddt.unpack
    def test_handle_processor_response_not_accepted(self, decision, exception):
        """ The handle_processor_response method should raise an exception if payment was not accepted. """

        response = self.generate_notification(self.basket, decision=decision)

        self.assertRaises(
            exception,
            self.processor.handle_processor_response,
            self.processor.normalize_processor_response(response),
            basket=self.basket
        )

    def test_handle_processor_response_invalid_auth_amount(self):
        """
        The handle_processor_response method should raise PartialAuthorizationError if the authorized amount
        differs from the requested amount.
        """
        response = self.generate_notification(self.basket, auth_amount='0.00')
        self.assertRaises(
            PartialAuthorizationError,
            self.processor.handle_processor_response,
            self.processor.normalize_processor_response(response),
            basket=self.basket
        )

    def test_handle_processor_response_duplicate_notification(self):
        """
        The handle_processor_response method should raise respective exception if there is already a
        payment notification and order existed with same or different transaction IDs.
        """
        notification = self.generate_notification(self.basket, billing_address=self.make_billing_address())
        self.client.post(reverse('cybersource:redirect'), notification)

        self.assertTrue(PaymentProcessorResponse.objects.filter(basket=self.basket).exists())
        self.assertTrue(Order.objects.filter(basket=self.basket).exists())

        # handle_processor_response should raise RedundantPaymentNotificationError for same transaction ID
        self.assertRaises(
            RedundantPaymentNotificationError,
            self.processor.handle_processor_response,
            self.processor.normalize_processor_response(notification),
            basket=self.basket
        )

        notification['transaction_id'] = '394934470384'
        notification['signature'] = self.generate_signature(self.processor.secret_key, notification)
        # handle_processor_response should raise ExcessivePaymentForOrderError for different transaction ID
        self.assertRaises(
            ExcessivePaymentForOrderError,
            self.processor.handle_processor_response,
            self.processor.normalize_processor_response(notification),
            basket=self.basket
        )

    @responses.activate
    def test_issue_credit(self):
        """
        Tests issue_credit operation for refunds.
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

        response = self.mock_refund_response(amount=amount, currency=currency, transaction_id=transaction_id,
                                             basket_id=basket.id)
        actual = self.processor.issue_credit(order.number, basket, source.reference, amount, currency)
        self.assertEqual(actual, transaction_id)

        # Verify PaymentProcessorResponse created
        self.assert_processor_response_recorded(self.processor.NAME, transaction_id, response, basket)

    @responses.activate
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
        with mock.patch.object(requests.Session, 'get', mock.Mock(side_effect=requests.Timeout)):
            self.assertRaises(GatewayError, self.processor.issue_credit, order.number, order.basket, source.reference,
                              amount, currency)
            self.assertEqual(source.amount_refunded, 0)

        # Test for declined transaction
        response = self.mock_refund_response(amount=amount, currency=currency, transaction_id=transaction_id,
                                             basket_id=basket.id, decision='DECLINE')
        self.assertRaises(GatewayError, self.processor.issue_credit, order.number, order.basket, source.reference,
                          amount, currency)
        self.assert_processor_response_recorded(self.processor.NAME, transaction_id, response, basket)
        self.assertEqual(source.amount_refunded, 0)

    def test_client_side_payment_url(self):
        """ Verify the property returns the Silent Order POST URL. """
        processor_config = settings.PAYMENT_PROCESSOR_CONFIG[self.partner.name.lower()][self.processor.NAME.lower()]
        expected = processor_config['sop_payment_page_url']
        self.assertEqual(self.processor.client_side_payment_url, expected)

    def test_get_template_name(self):
        """ Verify the method returns the path to the client-side template. """
        self.assertEqual(self.processor.get_template_name(), 'payment/cybersource.html')

    @responses.activate
    def test_request_apple_pay_authorization(self):
        """ The method should authorize and settle an Apple Pay payment with CyberSource. """
        basket = create_basket(owner=self.create_user(), site=self.site)

        billing_address = factories.BillingAddressFactory()
        payment_token = {
            'paymentData': {
                'version': 'EC_v1',
                'data': 'fake-data',
                'signature': 'fake-signature',
                'header': {
                    'ephemeralPublicKey': 'fake-key',
                    'publicKeyHash': 'fake-hash',
                    'transactionId': 'abc123'
                }
            },
            'paymentMethod': {
                'displayName': 'AmEx 1086',
                'network': 'AmEx',
                'type': 'credit'
            },
            'transactionIdentifier': 'DEADBEEF'
        }

        self.mock_cybersource_wsdl()
        self.mock_authorization_response(accepted=True)

        actual = self.processor.request_apple_pay_authorization(basket, billing_address, payment_token)
        self.assertEqual(actual.total, basket.total_incl_tax)
        self.assertEqual(actual.currency, basket.currency)
        self.assertEqual(actual.card_number, 'Apple Pay')
        self.assertEqual(actual.card_type, 'american_express')

    @responses.activate
    def test_request_apple_pay_authorization_rejected(self):
        """ The method should raise GatewayError if CyberSource rejects the payment. """
        self.mock_cybersource_wsdl()
        self.mock_authorization_response(accepted=False)

        basket = create_basket(site=self.site, owner=self.create_user())

        billing_address = factories.BillingAddressFactory()
        payment_token = {
            'paymentData': {
                'version': 'EC_v1',
                'data': 'fake-data',
                'signature': 'fake-signature',
                'header': {
                    'ephemeralPublicKey': 'fake-key',
                    'publicKeyHash': 'fake-hash',
                    'transactionId': 'abc123'
                }
            },
            'paymentMethod': {
                'displayName': 'AmEx 1086',
                'network': 'AmEx',
                'type': 'credit'
            },
            'transactionIdentifier': 'DEADBEEF'
        }

        with self.assertRaises(GatewayError):
            self.processor.request_apple_pay_authorization(basket, billing_address, payment_token)

    def test_request_apple_pay_authorization_error(self):
        """ The method should raise GatewayError if an error occurs while authorizing payment. """
        basket = create_basket(site=self.site, owner=self.create_user())

        with mock.patch('zeep.Client.__init__', side_effect=Exception):
            with self.assertRaises(GatewayError):
                self.processor.request_apple_pay_authorization(basket, None, None)


@ddt.ddt
class CybersourceRESTTests(CybersourceMixin, PaymentProcessorTestCaseMixin, CyberSourceRESTAPIMixin, TestCase):
    """ Tests for CyberSource payment processor. """

    processor_class = CybersourceREST
    processor_name = "cybersource-rest"

    # pylint: disable=line-too-long
    @ddt.data(
        (
            """{"links":{"_self":{"href":"/pts/v2/payments/6021683934456376603262","method":"GET"},"reversal":null,"capture":null,"customer":null,"payment_instrument":null,"shipping_address":null,"instrument_identifier":null},"id":"6021683934456376603262","submit_time_utc":null,"status":"DECLINED","reconciliation_id":null,"error_information":{"reason":"PROCESSOR_DECLINED","message":"Decline - General decline of the card. No other information provided by the issuing bank.","details":null},"client_reference_information":{"code":"EDX-43544589","submit_local_date_time":null,"owner_merchant_id":null},"processing_information":null,"processor_information":{"auth_indicator":null,"approval_code":null,"transaction_id":"460282531937765","network_transaction_id":"460282531937765","provider_transaction_id":null,"response_code":"005","response_code_source":null,"response_details":null,"response_category_code":null,"forwarded_acquirer_code":null,"avs":{"code":"D","code_raw":"D"},"card_verification":{"result_code":"M","result_code_raw":"M"},"merchant_advice":null,"electronic_verification_results":null,"ach_verification":null,"customer":null,"consumer_authentication_response":null,"system_trace_audit_number":null,"payment_account_reference_number":null,"transaction_integrity_code":null,"amex_verbal_auth_reference_number":null,"master_card_service_code":null,"master_card_service_reply_code":null,"master_card_authentication_type":null,"name":null,"routing":null,"merchant_number":null},"issuer_information":null,"payment_information":{"card":null,"tokenized_card":null,"account_features":{"account_type":null,"account_status":null,"balances":null,"balance_amount":null,"balance_amount_type":null,"currency":null,"balance_sign":null,"affluence_indicator":null,"category":"F","commercial":null,"group":null,"health_care":null,"payroll":null,"level3_eligible":null,"pinless_debit":null,"signature_debit":null,"prepaid":null,"regulated":null},"bank":null,"customer":null,"payment_instrument":null,"instrument_identifier":null,"shipping_address":null},"order_information":null,"point_of_sale_information":null,"installment_information":null,"token_information":null,"risk_information":null,"consumer_authentication_information":null}""",
            UnhandledCybersourceResponse(
                decision=Decision.decline,
                duplicate_payment=False,
                partial_authorization=False,
                currency=None,
                total=None,
                card_number='xxxx xxxx xxxx 1111',
                card_type=None,
                transaction_id="6021683934456376603262",
                order_id="EDX-43544589",
                raw_json=None,
            )
        ),
        (
            """{"links":{"_self":{"href":"/pts/v2/payments/6014090257646975704001","method":"GET"},"reversal":null,"capture":null,"customer":null,"payment_instrument":null,"shipping_address":null,"instrument_identifier":null},"id":"6014090257646975704001","submit_time_utc":"2020-09-29T19:50:26Z","status":"AUTHORIZED_PENDING_REVIEW","reconciliation_id":null,"error_information":{"reason":"CONTACT_PROCESSOR","message":"Decline - The issuing bank has questions about the request. You do not receive an authorization code programmatically, but you might receive one verbally by calling the processor.","details":null},"client_reference_information":{"code":"EDX-248645","submit_local_date_time":null,"owner_merchant_id":null},"processing_information":null,"processor_information":{"auth_indicator":null,"approval_code":null,"transaction_id":"558196000003814","network_transaction_id":"558196000003814","provider_transaction_id":null,"response_code":"001","response_code_source":null,"response_details":null,"response_category_code":null,"forwarded_acquirer_code":null,"avs":{"code":"Y","code_raw":"Y"},"card_verification":{"result_code":"2","result_code_raw":null},"merchant_advice":null,"electronic_verification_results":null,"ach_verification":null,"customer":null,"consumer_authentication_response":null,"system_trace_audit_number":null,"payment_account_reference_number":null,"transaction_integrity_code":null,"amex_verbal_auth_reference_number":null,"master_card_service_code":null,"master_card_service_reply_code":null,"master_card_authentication_type":null,"name":null,"routing":null,"merchant_number":null},"issuer_information":null,"payment_information":{"card":null,"tokenized_card":null,"account_features":{"account_type":null,"account_status":null,"balances":null,"balance_amount":null,"balance_amount_type":null,"currency":null,"balance_sign":null,"affluence_indicator":null,"category":"A","commercial":null,"group":null,"health_care":null,"payroll":null,"level3_eligible":null,"pinless_debit":null,"signature_debit":null,"prepaid":null,"regulated":null},"bank":null,"customer":null,"payment_instrument":null,"instrument_identifier":null,"shipping_address":null},"order_information":null,"point_of_sale_information":null,"installment_information":null,"token_information":null,"risk_information":null,"consumer_authentication_information":{"acs_rendering_type":null,"acs_transaction_id":null,"acs_url":null,"authentication_path":null,"authorization_payload":null,"authentication_transaction_id":null,"cardholder_message":null,"cavv":null,"cavv_algorithm":null,"challenge_cancel_code":null,"challenge_required":null,"decoupled_authentication_indicator":null,"directory_server_error_code":null,"directory_server_error_description":null,"ecommerce_indicator":null,"eci":null,"eci_raw":null,"effective_authentication_type":null,"ivr":null,"network_score":null,"pareq":null,"pares_status":null,"proof_xml":null,"proxy_pan":null,"sdk_transaction_id":null,"signed_pares_status_reason":null,"specification_version":null,"step_up_url":null,"three_ds_server_transaction_id":null,"ucaf_authentication_data":null,"ucaf_collection_indicator":null,"veres_enrolled":null,"white_list_status_source":null,"xid":null,"directory_server_transaction_id":null,"authentication_result":null,"authentication_status_msg":null,"indicator":null,"interaction_counter":null,"white_list_status":null}}""",
            UnhandledCybersourceResponse(
                decision=Decision.authorized_pending_review,
                duplicate_payment=False,
                partial_authorization=False,
                currency=None,
                total=None,
                card_number='xxxx xxxx xxxx 1111',
                card_type=None,
                transaction_id="6014090257646975704001",
                order_id="EDX-248645",
                raw_json=None,
            )
        ), (
            """{"links":{"_self":{"href":"/pts/v2/payments/6014073435566389304232","method":"GET"},"reversal":null,"capture":null,"customer":null,"payment_instrument":null,"shipping_address":null,"instrument_identifier":null},"id":"6014073435566389304232","submit_time_utc":"2020-09-29T19:22:24Z","status":"AUTHORIZED_PENDING_REVIEW","reconciliation_id":null,"error_information":{"reason":"CV_FAILED","message":"Soft Decline - The authorization request was approved by the issuing bank but declined by CyberSource because it did not pass the card verification number (CVN) check.","details":null},"client_reference_information":{"code":"EDX-43442011","submit_local_date_time":null,"owner_merchant_id":null},"processing_information":null,"processor_information":{"auth_indicator":null,"approval_code":"08369P","transaction_id":"MWEZQL3LE","network_transaction_id":"MWEZQL3LE","provider_transaction_id":null,"response_code":"000","response_code_source":null,"response_details":null,"response_category_code":null,"forwarded_acquirer_code":null,"avs":{"code":"Y","code_raw":"Y"},"card_verification":{"result_code":"N","result_code_raw":"N"},"merchant_advice":null,"electronic_verification_results":null,"ach_verification":null,"customer":null,"consumer_authentication_response":null,"system_trace_audit_number":null,"payment_account_reference_number":null,"transaction_integrity_code":null,"amex_verbal_auth_reference_number":null,"master_card_service_code":null,"master_card_service_reply_code":null,"master_card_authentication_type":null,"name":null,"routing":null,"merchant_number":null},"issuer_information":null,"payment_information":{"card":null,"tokenized_card":null,"account_features":{"account_type":null,"account_status":null,"balances":null,"balance_amount":null,"balance_amount_type":null,"currency":null,"balance_sign":null,"affluence_indicator":null,"category":"MWE","commercial":null,"group":null,"health_care":null,"payroll":null,"level3_eligible":null,"pinless_debit":null,"signature_debit":null,"prepaid":null,"regulated":null},"bank":null,"customer":null,"payment_instrument":null,"instrument_identifier":null,"shipping_address":null},"order_information":{"amount_details":{"total_amount":null,"authorized_amount":"50.00","currency":"USD"},"invoice_details":null},"point_of_sale_information":null,"installment_information":null,"token_information":null,"risk_information":null,"consumer_authentication_information":null}""",
            UnhandledCybersourceResponse(
                decision=Decision.authorized_pending_review,
                duplicate_payment=False,
                partial_authorization=False,
                currency="USD",
                total=Decimal(50),
                card_number='xxxx xxxx xxxx 1111',
                card_type=None,
                transaction_id="6014073435566389304232",
                order_id="EDX-43442011",
                raw_json=None,
            )
        ), (
            """{"links":{"_self":{"href":"/pts/v2/payments/6015729214586539504002","method":"GET"},"reversal":null,"capture":null,"customer":null,"payment_instrument":null,"shipping_address":null,"instrument_identifier":null},"id":"6015729214586539504002","submit_time_utc":"2020-10-01T17:22:02Z","status":"AUTHORIZED","reconciliation_id":null,"error_information":null,"client_reference_information":{"code":"EDX-248767","submit_local_date_time":null,"owner_merchant_id":null},"processing_information":null,"processor_information":{"auth_indicator":null,"approval_code":"831000","transaction_id":"558196000003814","network_transaction_id":"558196000003814","provider_transaction_id":null,"response_code":"000","response_code_source":null,"response_details":null,"response_category_code":null,"forwarded_acquirer_code":null,"avs":{"code":"Y","code_raw":"Y"},"card_verification":{"result_code":"3","result_code_raw":null},"merchant_advice":null,"electronic_verification_results":null,"ach_verification":null,"customer":null,"consumer_authentication_response":null,"system_trace_audit_number":null,"payment_account_reference_number":null,"transaction_integrity_code":null,"amex_verbal_auth_reference_number":null,"master_card_service_code":null,"master_card_service_reply_code":null,"master_card_authentication_type":null,"name":null,"routing":null,"merchant_number":null},"issuer_information":null,"payment_information":{"card":null,"tokenized_card":{"prefix":null,"suffix":null,"type":"001","assurance_level":null,"expiration_month":null,"expiration_year":null,"requestor_id":null},"account_features":{"account_type":null,"account_status":null,"balances":null,"balance_amount":null,"balance_amount_type":null,"currency":null,"balance_sign":null,"affluence_indicator":null,"category":"A","commercial":null,"group":null,"health_care":null,"payroll":null,"level3_eligible":null,"pinless_debit":null,"signature_debit":null,"prepaid":null,"regulated":null},"bank":null,"customer":null,"payment_instrument":null,"instrument_identifier":null,"shipping_address":null},"order_information":{"amount_details":{"total_amount":"900.00","authorized_amount":"900.00","currency":"USD"},"invoice_details":null},"point_of_sale_information":null,"installment_information":null,"token_information":null,"risk_information":null,"consumer_authentication_information":{"acs_rendering_type":null,"acs_transaction_id":null,"acs_url":null,"authentication_path":null,"authorization_payload":null,"authentication_transaction_id":null,"cardholder_message":null,"cavv":null,"cavv_algorithm":null,"challenge_cancel_code":null,"challenge_required":null,"decoupled_authentication_indicator":null,"directory_server_error_code":null,"directory_server_error_description":null,"ecommerce_indicator":null,"eci":null,"eci_raw":null,"effective_authentication_type":null,"ivr":null,"network_score":null,"pareq":null,"pares_status":null,"proof_xml":null,"proxy_pan":null,"sdk_transaction_id":null,"signed_pares_status_reason":null,"specification_version":null,"step_up_url":null,"three_ds_server_transaction_id":null,"ucaf_authentication_data":null,"ucaf_collection_indicator":null,"veres_enrolled":null,"white_list_status_source":null,"xid":null,"directory_server_transaction_id":null,"authentication_result":null,"authentication_status_msg":null,"indicator":null,"interaction_counter":null,"white_list_status":null}}""",
            UnhandledCybersourceResponse(
                decision=Decision.accept,
                duplicate_payment=False,
                partial_authorization=False,
                currency="USD",
                total=Decimal(900),
                card_number='xxxx xxxx xxxx 1111',
                card_type="visa",
                transaction_id="6015729214586539504002",
                order_id="EDX-248767",
                raw_json=None,
            )
        )
    )
    # pylint: enable=line-too-long
    @ddt.unpack
    def test_normalize_processor_response(
            self, processor_json, normalized_response
    ):
        """
        Verify the results of normalize_processor_response for a variety of messages.
        """
        # The normalized response should always have the same processed json as is being
        # loaded by the test.
        normalized_response.raw_json = json.loads(processor_json)

        processor_json = self.convertToCybersourceWireFormat(processor_json)
        processor_response = ApiClient().deserialize(
            mock.Mock(data=processor_json), 'PtsV2PaymentsPost201Response'
        )
        # Add a bogus JWT
        processor_response.decoded_payment_token = {
            'data': {'number': 'xxxx xxxx xxxx 1111'}
        }
        assert self.processor.normalize_processor_response(
            processor_response
        ) == normalized_response

    def test_get_transaction_parameters(self):
        """ Verify the processor returns the appropriate parameters required to complete a transaction. """
        raise SkipTest("Not yet implemented")

    def test_handle_processor_response(self):
        """ Verify that the processor creates the appropriate PaymentEvent and Source objects. """
        raise SkipTest("Not yet implemented")

    def test_issue_credit(self):
        """ Verify the payment processor responds appropriately to requests to issue credit/refund. """
        raise SkipTest("Not yet implemented")

    def test_issue_credit_error(self):
        """ Verify the payment processor responds appropriately if the payment gateway cannot issue a credit/refund. """
        raise SkipTest("Not yet implemented")

    def test_client_side_payment_url(self):
        raise SkipTest("No client side payment url for CybersourceREST")
