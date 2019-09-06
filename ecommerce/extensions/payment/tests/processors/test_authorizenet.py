import json
import base64
from mock import patch
from django.urls import reverse
from django.conf import settings
from lxml import objectify, etree
from authorizenet import apicontractsv1

from ecommerce.tests.testcases import TestCase
from ecommerce.core.url_utils import get_ecommerce_url
from ecommerce.extensions.payment.exceptions import (
    RefundError,
    MissingTransactionDetailError,
    PaymentProcessorResponseNotFound,
    MissingProcessorResponseCardInfo,
)
from ecommerce.extensions.test.factories import create_order
from ecommerce.extensions.test.authorizenet_utils import (
    get_authorizenet_refund_reponse_xml,
    get_authorizenet_transaction_reponse_xml,
    record_transaction_detail_processor_response,
)
from ecommerce.extensions.test.constants import (
    refund_error_response,
    refund_success_response,
    transaction_detail_response_error_data,
    hosted_payment_token_response_template,
    transaction_detail_response_success_data,
)
from ecommerce.extensions.payment.utils import LxmlObjectJsonEncoder
from ecommerce.extensions.payment.processors.authorizenet import AuthorizeNet
from ecommerce.extensions.payment.tests.processors.mixins import PaymentProcessorTestCaseMixin


class AuthorizeNetTests(PaymentProcessorTestCaseMixin, TestCase):
    processor_class = AuthorizeNet
    processor_name = 'authorizenet'

    def setUp(self):
        super(AuthorizeNetTests, self).setUp()
        self.transaction_id = "1111111111111111"
        self.refund_transaction_id = "2222222222222222"

    @patch('ecommerce.extensions.payment.processors.authorizenet.getHostedPaymentPageController', autospec=True)
    def test_get_transaction_parameters(self, mock_controller):
        """
            Verify the processor returns the appropriate parameters required to complete a transaction
        """
        token_api_response = objectify.fromstring( hosted_payment_token_response_template)
        mock_controller.return_value.getresponse.return_value = token_api_response
        actual_data = self.processor.get_transaction_parameters(self.basket, request=self.request)
        expected_data = {
            'payment_page_url': self.processor.autorizenet_redirect_url,
            'token': "test_token"
        }
        self.assertDictEqual(actual_data, expected_data)

    def test_get_authorizenet_payment_settings(self):
        """
            Verify the processor returns the required Authorize Net (sdk) setting object properly
        """
        course_id = self.basket.all_lines()[0].product.course_id
        course_id_hash = base64.b64encode(course_id.encode())

        redirect_url = reverse('authorizenet:redirect')
        ecommerce_base_url = get_ecommerce_url()
        return_url = '{}{}?course={}'.format(ecommerce_base_url, redirect_url, course_id_hash)

        payment_button_expected_setting_name = apicontractsv1.settingNameEnum.hostedPaymentButtonOptions
        payment_button_expected_setting_value = json.dumps({'text': 'Pay'})

        payment_return_expected_setting_name = apicontractsv1.settingNameEnum.hostedPaymentReturnOptions
        payment_return_configrations = {
            'url': return_url,
            'urlText': 'Continue',
            'cancelUrl': self.processor.cancel_url,
            'cancelUrlText': 'Cancel'
        }
        payment_return_expected_setting_value = json.dumps(payment_return_configrations)
        actual_settings = self.processor._get_authorizenet_payment_settings(self.basket)

        self.assertEqual(actual_settings.setting[0].settingName, payment_button_expected_setting_name)
        self.assertEqual(actual_settings.setting[0].settingValue, payment_button_expected_setting_value)
        self.assertEqual(actual_settings.setting[1].settingName, payment_return_expected_setting_name)
        self.assertEqual(actual_settings.setting[1].settingValue,payment_return_expected_setting_value)

    def test_get_authorizenet_lineitems(self):
        """
            Verify the processor returns the required Authorize Net (sdk) line items object properly
            containing all the information items from the basket.
        """
        expected_line_item = self.basket.all_lines()[0]
        expected_line_item_unit_price = expected_line_item.line_price_incl_tax_incl_discounts / expected_line_item.quantity

        actual_line_items_list = self.processor._get_authorizenet_lineitems(self.basket)
        actual_line_item = actual_line_items_list.lineItem[0]

        self.assertEqual(actual_line_item.itemId, expected_line_item.product.course_id)
        self.assertEqual(actual_line_item.name, expected_line_item.product.course_id)
        self.assertEqual(actual_line_item.description, expected_line_item.product.title)
        self.assertEqual(actual_line_item.quantity, expected_line_item.quantity)
        self.assertEqual(actual_line_item.unitPrice, expected_line_item_unit_price)

    @patch('ecommerce.extensions.payment.processors.authorizenet.getTransactionDetailsController', autospec=True)
    def test_get_transaction_detail_success(self, mock_controller):
        """
            Verify the processor returns the transaction_detail properly on receiving success response from
            AuthorizeNet (transaction detail) API
        """

        response_data = transaction_detail_response_success_data
        transaction_detail_xml = get_authorizenet_transaction_reponse_xml(
            self.transaction_id, self.basket, response_data)

        transaction_detail_response = objectify.fromstring(transaction_detail_xml)
        mock_controller.return_value.getresponse.return_value = transaction_detail_response

        expected_transaction_detail_object = objectify.fromstring(transaction_detail_xml)
        expected_transaction_detail_xml = etree.tostring(expected_transaction_detail_object)

        actual_transaction_detail_object = self.processor.get_transaction_detail(self.transaction_id)
        actual_transaction_detail_xml = etree.tostring(actual_transaction_detail_object)

        self.assertEqual(actual_transaction_detail_xml, expected_transaction_detail_xml)

    @patch('ecommerce.extensions.payment.processors.authorizenet.getTransactionDetailsController', autospec=True)
    def test_get_transaction_detail_error(self, mock_controller):
        """
            Verify the processor raises MissingTransactionDetailError on receiving error response from
            AuthorizeNet (transaction detail) API.
        """
        response_data = transaction_detail_response_error_data
        transaction_detail_xml = get_authorizenet_transaction_reponse_xml(
            self.transaction_id, self.basket, response_data)

        transaction_detail_response = objectify.fromstring(transaction_detail_xml)
        mock_controller.return_value.getresponse.return_value = transaction_detail_response

        self.assertRaises (
            MissingTransactionDetailError, self.processor.get_transaction_detail, self.transaction_id)

    def test_handle_processor_response(self):
        """
            Verify that the processor creates the appropriate PaymentEvent and Source objects.
        """
        response_data = transaction_detail_response_success_data
        transaction_detail_xml = get_authorizenet_transaction_reponse_xml(
            self.transaction_id, self.basket, response_data)
        transaction_response = objectify.fromstring(transaction_detail_xml)

        expected_transaction_dict = LxmlObjectJsonEncoder().encode(transaction_response)
        expected_transaction = transaction_response.transaction
        expected_card_info = expected_transaction.payment.creditCard

        actual_handled_response = self.processor.handle_processor_response(transaction_response, basket=self.basket)
        self.assertEqual(actual_handled_response.currency, self.basket.currency)
        self.assertEqual(actual_handled_response.total, float(expected_transaction.settleAmount))
        self.assertEqual(actual_handled_response.transaction_id, expected_transaction.transId)
        self.assertEqual(actual_handled_response.card_type, expected_card_info.cardType )
        self.assertEqual(actual_handled_response.card_number, expected_card_info.cardNumber )

        self.assert_processor_response_recorded(
            self.processor_name, expected_transaction.transId, expected_transaction_dict, basket=self.basket)

    @patch('ecommerce.extensions.payment.processors.authorizenet.createTransactionController', autospec=True)
    def test_issue_credit(self, mock_controller):
        """
            Tests issuing credit with AuthorizeNet processor
        """
        reference_transaction_id = self.transaction_id
        expected_transaction_id = self.refund_transaction_id

        record_transaction_detail_processor_response(self.processor, reference_transaction_id, self.basket)

        data = {
            "result_code": "Ok",
            "message_code": "I00001",
            "response_code": "1",
            "transaction_id": expected_transaction_id,
            "reference_transaction_id": reference_transaction_id,
            "sub_template": refund_success_response,
        }

        refund_response_xml = get_authorizenet_refund_reponse_xml(data)
        refund_response = objectify.fromstring(refund_response_xml)
        mock_controller.return_value.getresponse.return_value = refund_response

        expected_refund_transaction_dict = LxmlObjectJsonEncoder().encode(refund_response)
        order = create_order(basket=self.basket)
        actual_transaction_id = self.processor.issue_credit(
            order.number, order.basket, reference_transaction_id, order.total_incl_tax, order.currency)

        self.assertEqual(int(expected_transaction_id), actual_transaction_id)
        self.assert_processor_response_recorded(
            self.processor_name, actual_transaction_id, expected_refund_transaction_dict, basket=self.basket)

    @patch('ecommerce.extensions.payment.processors.authorizenet.createTransactionController', autospec=True)
    def test_issue_credit_error(self, mock_controller):
        """
            Verify the processor raises RefundError on receiving error response from AuthorizeNet (Refund) API.
        """
        reference_transaction_id = self.transaction_id
        expected_transaction_id = self.refund_transaction_id

        record_transaction_detail_processor_response(self.processor, reference_transaction_id, self.basket)

        data = {
            "result_code": "Error",
            "message_code": "E00001",
            "response_code": "3",
            "transaction_id": "0",
            "reference_transaction_id": reference_transaction_id,
            "sub_template": refund_error_response,
        }

        refund_response_xml = get_authorizenet_refund_reponse_xml(data)
        refund_response = objectify.fromstring(refund_response_xml)
        mock_controller.return_value.getresponse.return_value = refund_response

        order = create_order(basket=self.basket)
        self.assertRaises (
            RefundError, self.processor.issue_credit, order.number, order.basket, reference_transaction_id, order.total_incl_tax, order.currency
        )

    def test_issue_credit_for_missing_response_error(self):
        """
            Verify the processor raises PaymentProcessorResponseNotFound if there is no payment record
            of transaction_id for which refund has been requested.
        """
        reference_transaction_id = self.transaction_id
        order = create_order(basket=self.basket)
        self.assertRaises (
            PaymentProcessorResponseNotFound, self.processor.issue_credit, order.number, order.basket, reference_transaction_id, order.total_incl_tax, order.currency
        )
