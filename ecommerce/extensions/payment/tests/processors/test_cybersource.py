# -*- coding: utf-8 -*-
"""Unit tests of Cybersource payment processor implementation."""


import json
import sys
from decimal import Decimal
from unittest import SkipTest

import ddt
import mock
import requests
import responses
from CyberSource.api_client import ApiClient
from oscar.apps.payment.exceptions import GatewayError
from oscar.core.loading import get_model
from oscar.test import factories

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
        if sys.version_info > (3, 9):
            self.assertLessEqual(expected.items(), ppr.response.items())
        else:
            self.assertDictContainsSubset(expected, ppr.response)
        self.assertEqual(ppr.basket, basket)

        return ppr.id

    def test_handle_processor_response(self):
        """ Verify that the processor creates the appropriate PaymentEvent and Source objects. """
        raise SkipTest("No longer used")

    def test_client_side_payment_url(self):
        """ Verify that the processor creates the appropriate PaymentEvent and Source objects. """
        raise SkipTest("No longer used")

    def test_get_transaction_parameters(self):
        """ Verify that the processor creates the appropriate PaymentEvent and Source objects. """
        raise SkipTest("No longer used")

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
