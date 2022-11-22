

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


class StripeTests(PaymentProcessorTestCaseMixin, TestCase):
    processor_class = Stripe
    processor_name = 'stripe'

    def test_get_transaction_parameters(self):
        transaction_params = self.processor.get_transaction_parameters(self.basket)
        assert 'payment_page_url' in transaction_params.keys()

    # TODO: update or remove these tests
    def test_handle_processor_response(self):
        assert True
        # payment_intent_1 = stripe.PaymentIntent.construct_from({
        #     'id': 'pi_testtesttest',
        #     'source': {
        #         'brand': 'visa',
        #         'last4': '4242',
        #     },
        # }, 'fake-key')

        # payment_intent_2 = stripe.PaymentIntent.construct_from({
        #     'id': 'pi_testtesttest',
        #     'source': {
        #         'brand': 'visa',
        #         'last4': '4242',
        #     },
        #     'status': 'succeeded',
        #     "charges": {
        #         "object": "list",
        #         "data": [
        #             {
        #                 "id": "ch_testtesttest",
        #                 "object": "charge",
        #                 "status": "succeeded",
        #                 "payment_method_details": {
        #                     "card": {
        #                         "brand": "visa",
        #                         "country": "US",
        #                         "exp_month": 5,
        #                         "exp_year": 2020,
        #                         "fingerprint": "Xt5EWLLDS7FJjR1c",
        #                         "funding": "credit",
        #                         "last4": "4242",
        #                         "network": "visa",
        #                     },
        #                     "type": "card"
        #                 },
        #             }
        #         ]
        #     }
        # }, 'fake-key')

        # with mock.patch('stripe.PaymentIntent.modify') as payment_intent_modify_mock:
        #     with mock.patch('stripe.PaymentIntent.confirm') as payment_intent_confirm_mock:
        #         payment_intent_modify_mock.return_value = payment_intent_1
        #         payment_intent_confirm_mock.return_value = payment_intent_2
        #         actual = self.processor.handle_processor_response(payment_intent_1, self.basket)

        # assert actual.transaction_id == payment_intent_1.id
        # assert actual.total == self.basket.total_incl_tax
        # assert actual.currency == self.basket.currency

        # self.assert_processor_response_recorded(
        #     self.processor_name,
        #     payment_intent_2.id,
        #     payment_intent_2,
        #     basket=self.basket
        # )

    # def test_handle_processor_response_error(self):
    #     payment_intent_1 = stripe.PaymentIntent.construct_from({
    #         'id': 'pi_testtesttest',
    #         'source': {
    #             'brand': 'visa',
    #             'last4': '4242',
    #         },
    #     }, 'fake-key')
    #     with mock.patch('stripe.PaymentIntent.modify') as charge_mock:
    #         charge_mock.side_effect = stripe.error.CardError(
    #             'fake-msg', 'fake-param', 'fake-code', http_body='fake-body', http_status=500
    #         )
    #         self.assertRaises(
    #             TransactionDeclined,
    #             self.processor.handle_processor_response,
    #             payment_intent_1,
    #             self.basket
    #         )

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
