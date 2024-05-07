

import json
import logging

import mock
import stripe
from oscar.apps.payment.exceptions import GatewayError
from oscar.core.loading import get_model

from ecommerce.extensions.payment.processors.stripe import Stripe
from ecommerce.extensions.payment.tests.processors.mixins import PaymentProcessorTestCaseMixin
from ecommerce.extensions.test.factories import create_order
from ecommerce.tests.testcases import TestCase

log = logging.getLogger(__name__)

BillingAddress = get_model('order', 'BillingAddress')
Country = get_model('address', 'Country')

STRIPE_TEST_FIXTURE_PATH = 'ecommerce/extensions/payment/tests/views/fixtures/test_stripe_test_payment_flow.json'


class StripeTests(PaymentProcessorTestCaseMixin, TestCase):
    processor_class = Stripe
    processor_name = 'stripe'

    def _get_response_data(self, response_type):
        with open(STRIPE_TEST_FIXTURE_PATH, 'r') as fixtures:  # pylint: disable=unspecified-encoding
            return json.load(fixtures)['happy_path'][response_type]

    def test_get_transaction_parameters(self):
        transaction_params = self.processor.get_transaction_parameters(self.basket)
        assert 'payment_page_url' in transaction_params.keys()

    def test_handle_processor_response(self):
        with mock.patch('stripe.PaymentIntent.modify') as mock_modify:
            mock_modify.return_value = self._get_response_data('modify_resp')
            with mock.patch('stripe.PaymentIntent.confirm') as mock_confirm:
                confirm_response_data = self._get_response_data('confirm_resp')
                mock_confirm.return_value = confirm_response_data
                response = {
                    'payment_intent_id': confirm_response_data['id'],
                    'skus': self.basket.lines.first().stockrecord.partner_sku,
                    'dynamic_payment_methods_enabled': 'false'
                }
                actual = self.processor.handle_processor_response(response, self.basket)

                assert actual.transaction_id == confirm_response_data['id']
                assert actual.total == self.basket.total_incl_tax
                assert actual.currency == self.basket.currency

                self.assert_processor_response_recorded(
                    self.processor_name,
                    confirm_response_data['id'],
                    confirm_response_data,
                    basket=self.basket
                )

    def test_handle_processor_response_error(self):
        with self.assertLogs(level='ERROR') as logger:
            with mock.patch('stripe.PaymentIntent.modify') as mock_modify:
                mock_modify.return_value = self._get_response_data('modify_resp')
                with mock.patch('stripe.PaymentIntent.confirm') as mock_confirm:
                    mock_confirm.side_effect = stripe.error.CardError(
                        'fake-msg', 'fake-param', 'fake-code', http_body='fake-body', http_status=500
                    )
                    confirm_response_data = self._get_response_data('confirm_resp')
                    self.assertRaises(
                        stripe.error.CardError,
                        self.processor.handle_processor_response,
                        confirm_response_data,
                        self.basket
                    )
                    self.assertIn('Card Error for basket [{}]'.format(self.basket.id), logger.output[0])

    def test_issue_credit(self):
        charge_reference_number = '9436'
        refund = stripe.Refund.construct_from({
            'id': '946',
        }, 'fake-key')
        order = create_order(basket=self.basket)

        with mock.patch('stripe.Refund.create') as refund_mock:
            refund_mock.return_value = refund
            self.processor.issue_credit(
                order.number,
                order.basket,
                charge_reference_number,
                order.total_incl_tax,
                order.currency,
            )
            refund_mock.assert_called_once_with(
                payment_intent=charge_reference_number,
                amount=2000,
            )

        self.assert_processor_response_recorded(self.processor_name, refund.id, refund, basket=self.basket)

    def test_issue_credit_error(self):
        order = create_order(basket=self.basket)

        with mock.patch('stripe.Refund.create') as refund_mock:
            refund_mock.side_effect = stripe.error.APIError
            self.assertRaises(
                GatewayError, self.processor.issue_credit, order.number, order.basket, '123', order.total_incl_tax,
                order.currency
            )

    def test_issue_credit_error_invalid_request(self):
        """
        Verify InvalidRequest errors with the charge_already_refunded code
        return the id of the refund that already took place.
        """
        order = create_order(basket=self.basket)

        with mock.patch('stripe.Refund.create') as refund_mock:
            refund_mock.side_effect = stripe.error.InvalidRequestError('Oops!', {}, 'charge_already_refunded')

            with mock.patch('stripe.Refund.list') as list_mock:
                charge_reference_number = '9436'
                refund = stripe.Refund.construct_from({
                    'id': '946',
                }, 'fake-key')
                list_mock.return_value = {
                    'data': [refund]
                }

                result = self.processor.issue_credit(
                    order.number,
                    order.basket,
                    charge_reference_number,
                    order.total_incl_tax,
                    order.currency,
                )
                assert result == '946'

    def test_issue_credit_error_invalid_request_not_already_refunded(self):
        """
        Verify InvalidRequest errors with any non "already_refunded" codes
        raise an error.
        """
        order = create_order(basket=self.basket)

        with mock.patch('stripe.Refund.create') as refund_mock:
            refund_mock.side_effect = stripe.error.InvalidRequestError('Oops!', {}, 'charge_declined')

            with mock.patch('stripe.Refund.list') as list_mock:
                charge_reference_number = '9436'
                refund = stripe.Refund.construct_from({
                    'id': '946',
                }, 'fake-key')
                list_mock.return_value = {
                    'data': [refund]
                }

                self.assertRaises(
                    stripe.error.InvalidRequestError,
                    self.processor.issue_credit,
                    order.number,
                    order.basket,
                    charge_reference_number,
                    order.total_incl_tax,
                    order.currency,
                )
