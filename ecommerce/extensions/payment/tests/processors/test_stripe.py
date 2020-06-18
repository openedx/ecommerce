

import logging

import mock
import stripe
from oscar.apps.payment.exceptions import GatewayError, TransactionDeclined
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
        self.assertRaises(NotImplementedError, self.processor.get_transaction_parameters, self.basket)

    def test_handle_processor_response(self):
        token = 'abc123'
        charge = stripe.Charge.construct_from({
            'id': '2404',
            'source': {
                'brand': 'American Express',
                'last4': '1986',
            },
        }, 'fake-key')

        with mock.patch('stripe.Charge.create') as charge_mock:
            charge_mock.return_value = charge

            actual = self.processor.handle_processor_response(token, self.basket)

            charge_mock.assert_called_once_with(
                amount=str((self.basket.total_incl_tax * 100).to_integral_value()),
                currency=self.basket.currency,
                source=token,
                description=self.basket.order_number,
                metadata={'order_number': self.basket.order_number}
            )

        assert actual.transaction_id == charge.id
        assert actual.total == self.basket.total_incl_tax
        assert actual.currency == self.basket.currency
        assert actual.card_number == charge.source.last4
        assert actual.card_type == 'american_express'

        self.assert_processor_response_recorded(self.processor_name, charge.id, charge, basket=self.basket)

    def test_handle_processor_response_error(self):
        with mock.patch('stripe.Charge.create') as charge_mock:
            charge_mock.side_effect = stripe.error.CardError(
                'fake-msg', 'fake-param', 'fake-code', http_body='fake-body', http_status=500
            )
            self.assertRaises(TransactionDeclined, self.processor.handle_processor_response, 'fake-token', self.basket)

    def test_issue_credit(self):
        charge_reference_number = '9436'
        refund = stripe.Refund.construct_from({
            'id': '946',
        }, 'fake-key')
        order = create_order(basket=self.basket)

        with mock.patch('stripe.Refund.create') as refund_mock:
            refund_mock.return_value = refund
            self.processor.issue_credit(order.number, order.basket, charge_reference_number, order.total_incl_tax,
                                        order.currency)
            refund_mock.assert_called_once_with(charge=charge_reference_number)

        self.assert_processor_response_recorded(self.processor_name, refund.id, refund, basket=self.basket)

    def test_issue_credit_error(self):
        order = create_order(basket=self.basket)

        with mock.patch('stripe.Refund.create') as refund_mock:
            refund_mock.side_effect = stripe.error.APIError
            self.assertRaises(
                GatewayError, self.processor.issue_credit, order.number, order.basket, '123', order.total_incl_tax,
                order.currency
            )

    def assert_addresses_equal(self, actual, expected):
        for field in ('first_name', 'last_name', 'line1', 'line2', 'line3', 'line4', 'postcode', 'state', 'country'):
            assert getattr(actual, field) == getattr(expected, field), 'The value of {} differs'.format(field)

    def test_get_address_from_token(self):
        country, __ = Country.objects.get_or_create(iso_3166_1_a2='US')
        expected = BillingAddress(
            first_name='Richard White',
            last_name='',
            line1='1201 E. 8th Street',
            line2='Suite 216',
            line4='Dallas',
            postcode='75203',
            state='TX',
            country=country
        )
        token = stripe.Token.construct_from({
            'id': 'tok_test',
            'card': {
                'address_city': 'Dallas',
                'address_country': 'US',
                'address_line1': '1201 E. 8th Street',
                'address_line2': 'Suite 216',
                'address_state': 'TX',
                'address_zip': '75203',
                'name': 'Richard White',
            },
        }, 'fake-key')

        with mock.patch('stripe.Token.retrieve') as token_mock:
            token_mock.return_value = token
            self.assert_addresses_equal(self.processor.get_address_from_token(token.id), expected)

    def test_get_address_from_token_with_optional_fields(self):
        country, __ = Country.objects.get_or_create(iso_3166_1_a2='US')
        expected = BillingAddress(
            first_name='Ned Green',
            last_name='',
            line1='3111 Bonnie View Road',
            line2='',
            line4='Dallas',
            postcode='',
            state='',
            country=country
        )
        token = stripe.Token.construct_from({
            'id': 'tok_test',
            'card': {
                'address_city': 'Dallas',
                'address_country': 'US',
                'address_line1': '3111 Bonnie View Road',
                'address_line2': None,
                'address_state': None,
                # NOTE: This field is intentionally excluded to simulate the API field missing.
                # 'address_zip': None,
                'name': 'Ned Green',
            },
        }, 'fake-key')

        with mock.patch('stripe.Token.retrieve') as token_mock:
            token_mock.return_value = token
            self.assert_addresses_equal(self.processor.get_address_from_token(token.id), expected)
