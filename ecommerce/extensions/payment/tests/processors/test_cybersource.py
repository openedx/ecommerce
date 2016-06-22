# -*- coding: utf-8 -*-
"""Unit tests of Cybersource payment processor implementation."""
from __future__ import unicode_literals

import copy
import datetime
from uuid import UUID

import ddt
import httpretty
import mock
from django.conf import settings
from django.test import override_settings
from oscar.apps.payment.exceptions import UserCancelled, TransactionDeclined, GatewayError
from oscar.core.loading import get_model
from oscar.test import factories
from threadlocals.threadlocals import get_current_request

from ecommerce.core.constants import ISO_8601_FORMAT
from ecommerce.extensions.payment.exceptions import (
    InvalidSignatureError, InvalidCybersourceDecision, PartialAuthorizationError
)
from ecommerce.extensions.payment.processors.cybersource import Cybersource, suds_response_to_dict
from ecommerce.extensions.payment.tests.mixins import CybersourceMixin
from ecommerce.extensions.payment.tests.processors.mixins import PaymentProcessorTestCaseMixin
from ecommerce.tests.testcases import TestCase

PaymentEventType = get_model('order', 'PaymentEventType')
SourceType = get_model('payment', 'SourceType')


@ddt.ddt
class CybersourceTests(CybersourceMixin, PaymentProcessorTestCaseMixin, TestCase):
    """ Tests for CyberSource payment processor. """
    PI_DAY = datetime.datetime(2015, 3, 14, 9, 26, 53)
    UUID = 'UUID'

    processor_class = Cybersource
    processor_name = 'cybersource'

    def get_expected_transaction_parameters(self, transaction_uuid, include_level_2_3_details=True):
        """
        Builds expected transaction parameters dictionary
        """
        configuration = settings.PAYMENT_PROCESSOR_CONFIG['edx'][self.processor_name]
        access_key = configuration['access_key']
        profile_id = configuration['profile_id']

        expected = {
            'access_key': access_key,
            'profile_id': profile_id,
            'signed_field_names': '',
            'unsigned_field_names': '',
            'signed_date_time': self.PI_DAY.strftime(ISO_8601_FORMAT),
            'locale': settings.LANGUAGE_CODE,
            'transaction_type': 'sale',
            'reference_number': self.basket.order_number,
            'amount': unicode(self.basket.total_incl_tax),
            'currency': self.basket.currency,
            'consumer_id': self.basket.owner.username,
            'override_custom_receipt_page': '{}?order_number={}'.format(self.processor.receipt_page_url,
                                                                    self.basket.order_number),
            'override_custom_cancel_page': self.processor.cancel_page_url,
            'merchant_defined_data1': self.course.id,
            'merchant_defined_data2': self.CERTIFICATE_TYPE,
        }

        if include_level_2_3_details:
            expected.update({
                'line_item_count': self.basket.lines.count(),
                'amex_data_taa1': get_current_request().site.name,
                'purchasing_level': '3',
                'user_po': 'BLANK',
            })

            for index, line in enumerate(self.basket.lines.all()):
                expected['item_{}_code'.format(index)] = line.product.get_product_class().slug
                expected['item_{}_discount_amount '.format(index)] = str(line.discount_value)
                expected['item_{}_gross_net_indicator'.format(index)] = 'Y'
                expected['item_{}_name'.format(index)] = line.product.title
                expected['item_{}_quantity'.format(index)] = line.quantity
                expected['item_{}_sku'.format(index)] = line.stockrecord.partner_sku
                expected['item_{}_tax_amount'.format(index)] = str(line.line_tax)
                expected['item_{}_tax_rate'.format(index)] = '0'
                expected['item_{}_total_amount '.format(index)] = str(line.line_price_incl_tax_incl_discounts)
                expected['item_{}_unit_of_measure'.format(index)] = 'ITM'
                expected['item_{}_unit_price'.format(index)] = str(line.unit_price_incl_tax)

        signed_field_names = expected.keys() + ['transaction_uuid']
        expected['signed_field_names'] = ','.join(sorted(signed_field_names))

        # Copy the UUID value so that we can properly generate the signature. We will validate the UUID below.
        expected['transaction_uuid'] = transaction_uuid
        expected['signature'] = self.generate_signature(self.processor.secret_key, expected)

        return expected

    def assert_correct_transaction_parameters(self, include_level_2_3_details=True):
        """ Verifies the processor returns the correct parameters required to complete a transaction.

         Arguments
            include_level_23_details (bool): Determines if Level 2/3 details should be included in the parameters.
        """
        # Patch the datetime object so that we can validate the signed_date_time field
        with mock.patch.object(Cybersource, 'utcnow', return_value=self.PI_DAY):
            # NOTE (CCB): Instantiate a new processor object to ensure we reload any overridden settings.
            actual = self.processor_class().get_transaction_parameters(self.basket)

        expected = self.get_expected_transaction_parameters(actual['transaction_uuid'], include_level_2_3_details)
        self.assertDictContainsSubset(expected, actual)

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

    def test_is_signature_valid(self):
        """ Verify that the is_signature_valid method properly validates the response's signature. """

        # Empty data should never be valid
        self.assertFalse(self.processor.is_signature_valid({}))

        # The method should return False for responses with invalid signatures.
        response = {
            'signed_field_names': 'field_1,field_2,signed_field_names',
            'field_2': 'abc',
            'field_1': '123',
            'signature': 'abc123=='
        }
        self.assertFalse(self.processor.is_signature_valid(response))

        # The method should return True if the signature is valid.
        del response['signature']
        response['signature'] = self.generate_signature(self.processor.secret_key, response)
        self.assertTrue(self.processor.is_signature_valid(response))

    def test_handle_processor_response(self):
        """ Verify the processor creates the appropriate PaymentEvent and Source objects. """

        response = self.generate_notification(self.processor.secret_key, self.basket)
        reference = response['transaction_id']
        source, payment_event = self.processor.handle_processor_response(response, basket=self.basket)

        # Validate the Source
        source_type = SourceType.objects.get(code=self.processor.NAME)
        label = response['req_card_number']
        self.assert_basket_matches_source(
            self.basket,
            source,
            source_type,
            reference,
            label,
            card_type=self.DEFAULT_CARD_TYPE
        )

        # Validate PaymentEvent
        paid_type = PaymentEventType.objects.get(code='paid')
        amount = self.basket.total_incl_tax
        self.assert_valid_payment_event_fields(payment_event, amount, paid_type, self.processor.NAME, reference)

    def test_handle_processor_response_invalid_signature(self):
        """
        The handle_processor_response method should raise an InvalidSignatureError if the response's
        signature is not valid.
        """
        response = self.generate_notification(self.processor.secret_key, self.basket)
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

        response = self.generate_notification(self.processor.secret_key, self.basket, decision=decision)
        self.assertRaises(exception, self.processor.handle_processor_response, response, basket=self.basket)

    def test_handle_processor_response_invalid_auth_amount(self):
        """
        The handle_processor_response method should raise PartialAuthorizationError if the authorized amount
        differs from the requested amount.
        """
        response = self.generate_notification(self.processor.secret_key, self.basket, auth_amount='0.00')
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
            self.processor.issue_credit(source, amount, currency)

        # Verify PaymentProcessorResponse created
        self.assert_processor_response_recorded(self.processor.NAME, transaction_id,
                                                suds_response_to_dict(cs_soap_mock().runTransaction()),
                                                basket)

        # Verify Source updated
        self.assertEqual(source.amount_refunded, amount)

        # Verify PaymentEvent created
        paid_type = PaymentEventType.objects.get(code='refunded')
        payment_event = order.payment_events.first()
        self.assert_valid_payment_event_fields(payment_event, amount, paid_type, self.processor.NAME, transaction_id)

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
