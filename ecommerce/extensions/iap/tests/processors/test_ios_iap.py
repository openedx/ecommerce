# -*- coding: utf-8 -*-
"""Unit tests of IOS IAP payment processor implementation."""


import uuid
from urllib.parse import urljoin

import ddt
import mock
from django.test import RequestFactory
from django.urls import reverse
from oscar.apps.payment.exceptions import GatewayError, PaymentError
from oscar.core.loading import get_model
from testfixtures import LogCapture

from ecommerce.core.tests import toggle_switch
from ecommerce.core.url_utils import get_ecommerce_url
from ecommerce.extensions.checkout.utils import get_receipt_page_url
from ecommerce.extensions.iap.api.v1.constants import DISABLE_REDUNDANT_PAYMENT_CHECK_MOBILE_SWITCH_NAME
from ecommerce.extensions.iap.api.v1.ios_validator import IOSValidator
from ecommerce.extensions.iap.models import PaymentProcessorResponseExtension
from ecommerce.extensions.iap.processors.ios_iap import IOSIAP
from ecommerce.extensions.payment.exceptions import RedundantPaymentNotificationError
from ecommerce.extensions.payment.tests.processors.mixins import PaymentProcessorTestCaseMixin
from ecommerce.tests.testcases import TestCase

PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')


@ddt.ddt
class IOSIAPTests(PaymentProcessorTestCaseMixin, TestCase):
    """
    Tests for the IOSIAP payment processor.
    """

    processor_class = IOSIAP
    processor_name = 'ios-iap'

    @classmethod
    def setUpClass(cls):
        """
        Class set up - setting static up paypal sdk configuration to be used in test methods
        """
        super(IOSIAPTests, cls).setUpClass()  # required to pass CI build

    def setUp(self):
        """
        setUp method
        """
        super(IOSIAPTests, self).setUp()

        # Dummy request from which an HTTP Host header can be extracted during
        # construction of absolute URLs
        self.request = RequestFactory().post('/')
        self.processor_response_log = (
            u"Failed to execute IOSInAppPurchase payment on attempt [{attempt_count}]. "
            u"IOSInAppPurchase's response was recorded in entry [{entry_id}]."
        )
        self.RETURN_DATA = {
            'transactionId': 'test_id',
            'originalTransactionId': 'original_test_id',
            'productId': 'test_product_id',
            'purchaseToken': 'inapp:test.edx.edx:ios.test.purchased',
            'price': 40.25,
            'currency_code': 'USD',
        }
        self.mock_validation_response = {
            'environment': 'Sandbox',
            'receipt': {
                'bundle_id': 'test_bundle_id',
                'in_app': [
                    {
                        'in_app_ownership_type': 'PURCHASED',
                        'original_transaction_id': 'very_old_purchase_id',
                        'product_id': 'org.edx.mobile.test_product1',
                        'purchase_date_ms': '1676562309000',
                        'transaction_id': 'vaery_old_purchase_id'
                    },
                    {
                        'in_app_ownership_type': 'PURCHASED',
                        'original_transaction_id': 'old_purchase_id',
                        'product_id': 'org.edx.mobile.test_product3',
                        'purchase_date_ms': '1676562544000',
                        'transaction_id': 'old_purchase_id'
                    },
                    {
                        'in_app_ownership_type': 'PURCHASED',
                        'original_transaction_id': 'original_test_id',
                        'product_id': 'test_product_id',
                        'purchase_date_ms': '1676562978000',
                        'transaction_id': 'test_id'
                    }
                ],
                'receipt_creation_date_ms': '1676562978000',
            }
        }

    def _get_receipt_url(self):
        """
        DRY helper for getting receipt page URL.
        """
        return get_receipt_page_url(self.request, self.site.siteconfiguration)

    def test_get_transaction_parameters(self):
        """
        Verify the processor returns the appropriate parameters required to complete a transaction.
        """
        expected = {
            'payment_page_url': urljoin(get_ecommerce_url(), reverse('iap:iap-execute')),
        }
        actual = self.processor.get_transaction_parameters(self.basket)
        self.assertEqual(actual, expected)

    def test_is_payment_redundant(self):
        """
        Test that True is returned only if no PaymentProcessorResponseExtension entry is found with
        the given original_transaction_id.
        """
        original_transaction_id = str(uuid.uuid4())
        result = self.processor.is_payment_redundant(original_transaction_id=original_transaction_id)
        self.assertFalse(result)

        processor_response = PaymentProcessorResponse.objects.create(
            transaction_id=original_transaction_id, processor_name=self.processor_name)
        PaymentProcessorResponseExtension.objects.create(
            processor_response=processor_response, original_transaction_id=original_transaction_id)
        result = self.processor.is_payment_redundant(original_transaction_id=original_transaction_id)
        self.assertTrue(result)

    @mock.patch.object(IOSValidator, 'validate')
    def test_handle_processor_response_gateway_error(self, mock_ios_validator):
        """
        Verify that the processor creates the appropriate PaymentEvent and Source objects.
        """
        mock_ios_validator.return_value = {
            'error': 'Invalid receipt'
        }
        product_id = self.RETURN_DATA.get('productId')

        logger_name = 'ecommerce.extensions.iap.processors.ios_iap'
        with LogCapture(logger_name) as ios_iap_logger:
            with self.assertRaises(GatewayError):
                handled_response = self.processor.handle_processor_response(self.RETURN_DATA, basket=self.basket)
                self.assert_processor_response_recorded(
                    self.processor_name, handled_response.get('error'), handled_response,
                    basket=self.basket
                )
                ppr = PaymentProcessorResponse.objects.filter(
                    processor_name=self.processor_name
                ).latest('created')
                ios_iap_logger.check_present(
                    (
                        logger_name,
                        'WARNING',
                        "Failed to execute ios IAP payment for [{}] on attempt [{}]. "
                        "IOS IAP's response was recorded in entry [{}].".format(
                            product_id,
                            1,
                            ppr.id
                        ),
                    ),
                    (
                        logger_name,
                        'ERROR',
                        "Failed to execute ios IAP payment for [%s]. "
                        "IOS IAP's response was recorded in entry [%d].".format(
                            product_id,
                            ppr.id
                        ),
                    ),
                )

    @mock.patch.object(IOSValidator, 'validate')
    def test_handle_processor_response_payment_error(self, mock_ios_validator):
        """
        Verify that appropriate PaymentError is raised in absence of originalTransactionId parameter.
        """
        modified_validation_response = self.mock_validation_response
        modified_validation_response['receipt']['in_app'][2].pop('original_transaction_id')
        mock_ios_validator.return_value = modified_validation_response
        with self.assertRaises(PaymentError):
            modified_return_data = self.RETURN_DATA
            modified_return_data.pop('originalTransactionId')

            self.processor.handle_processor_response(modified_return_data, basket=self.basket)

    @mock.patch.object(IOSIAP, 'is_payment_redundant')
    @mock.patch.object(IOSValidator, 'validate')
    def test_handle_processor_response_redundant_error(self, mock_ios_validator, mock_payment_redundant):
        """
        Verify that appropriate RedundantPaymentNotificationError is raised in case payment with same
        originalTransactionId exists for any edx user.
        """
        mock_ios_validator.return_value = self.mock_validation_response
        mock_payment_redundant.return_value = True
        toggle_switch(DISABLE_REDUNDANT_PAYMENT_CHECK_MOBILE_SWITCH_NAME, False)

        with self.assertRaises(RedundantPaymentNotificationError):
            self.processor.handle_processor_response(self.RETURN_DATA, basket=self.basket)

    @mock.patch.object(IOSValidator, 'validate')
    def test_handle_processor_response(self, mock_ios_validator):  # pylint: disable=arguments-differ
        """
        Verify that the processor creates the appropriate PaymentEvent and Source objects.
        """
        mock_ios_validator.return_value = self.mock_validation_response

        handled_response = self.processor.handle_processor_response(self.RETURN_DATA, basket=self.basket)
        self.assertEqual(handled_response.currency, self.basket.currency)
        self.assertEqual(handled_response.total, self.basket.total_incl_tax)
        self.assertEqual(handled_response.transaction_id, self.RETURN_DATA['transactionId'])
        self.assertIsNone(handled_response.card_type)

    def test_issue_credit(self):
        """
        Tests issuing credit/refund with IOSInAppPurchase processor.
        """
        refund_id = "test id"
        result = self.processor.issue_credit(refund_id, refund_id, refund_id, refund_id, refund_id)
        self.assertEqual(refund_id, result)

    def test_issue_credit_error(self):
        """
        Tests issuing credit/refund with IOSInAppPurchase processor.
        """
        refund_id = "test id"
        result = self.processor.issue_credit(refund_id, refund_id, refund_id, refund_id, refund_id)
        self.assertEqual(refund_id, result)

    @mock.patch.object(IOSValidator, 'validate')
    def test_payment_processor_response_created(self, mock_ios_validator):
        """
        Verify that the PaymentProcessor object is created as expected.
        """
        mock_ios_validator.return_value = self.mock_validation_response
        transaction_id = self.RETURN_DATA.get('transactionId')

        self.processor.handle_processor_response(self.RETURN_DATA, basket=self.basket)
        payment_processor_response = PaymentProcessorResponse.objects.filter(transaction_id=transaction_id)
        self.assertTrue(payment_processor_response.exists())
        self.assertEqual(payment_processor_response.first().processor_name, self.processor_name)
        self.assertEqual(payment_processor_response.first().response, self.mock_validation_response)

    @mock.patch.object(IOSValidator, 'validate')
    def test_payment_processor_response_extension_created(self, mock_ios_validator):
        """
        Verify that the PaymentProcessorExtension object is created as expected.
        """
        mock_ios_validator.return_value = self.mock_validation_response
        transaction_id = self.RETURN_DATA.get('transactionId')
        original_transaction_id = self.RETURN_DATA.get('originalTransactionId')
        price = str(self.RETURN_DATA.get('price'))
        currency_code = self.RETURN_DATA.get('currency_code')

        self.processor.handle_processor_response(self.RETURN_DATA, basket=self.basket)
        payment_processor_response = PaymentProcessorResponse.objects.filter(transaction_id=transaction_id)
        payment_processor_response_extension = payment_processor_response.first().extension
        self.assertIsNotNone(payment_processor_response_extension)
        self.assertEqual(payment_processor_response_extension.original_transaction_id, original_transaction_id)
        self.assertEqual(payment_processor_response_extension.meta_data.get('price'), price)
        self.assertEqual(payment_processor_response_extension.meta_data.get('currency_code'), currency_code)
