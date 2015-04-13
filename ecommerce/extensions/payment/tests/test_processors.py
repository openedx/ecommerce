# -*- coding: utf-8 -*-
"""Unit tests of payment processor implementations."""
from collections import OrderedDict
import datetime
from decimal import Decimal as D
import logging

import ddt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
import mock
from nose.tools import raises
from oscar.test import factories

import ecommerce.extensions.payment.processors as processors
from ecommerce.extensions.order.models import Order
from ecommerce.extensions.payment.processors import BasePaymentProcessor, Cybersource, SingleSeatCybersource
from ecommerce.extensions.payment.errors import ExcessiveMerchantDefinedData, UnsupportedProductError
from ecommerce.extensions.payment.constants import CybersourceConstants as CS
from ecommerce.extensions.payment.constants import ProcessorConstants as PC
from ecommerce.extensions.fulfillment.status import ORDER


User = get_user_model()


class PaymentProcessorTestCase(TestCase):
    """Base test class for payment processor classes."""
    ORDER_NUMBER = '1'

    def setUp(self):
        # Override all loggers, suppressing logging calls of severity CRITICAL and below
        logging.disable(logging.CRITICAL)

        user = User.objects.create_user(
            username='Gus', email='gustavo@lospolloshermanos.com', password='the-chicken-man'
        )

        self.product_class = factories.ProductClassFactory(
            name='Seat',
            requires_shipping=False,
            track_stock=False
        )

        product_attribute = factories.ProductAttributeFactory(
            name='course_key',
            code='course_key',
            product_class=self.product_class,
            type='text'
        )

        fried_chicken = factories.ProductFactory(
            structure='parent',
            title=u'𝑭𝒓𝒊𝒆𝒅 𝑪𝒉𝒊𝒄𝒌𝒆𝒏',
            product_class=self.product_class,
            stockrecords=None,
        )

        factories.ProductAttributeValueFactory(
            attribute=product_attribute,
            product=fried_chicken,
            value_text='pollos/chickenX/2015'
        )

        pollos_hermanos = factories.ProductFactory(
            structure='child',
            parent=fried_chicken,
            title=u'𝕃𝕠𝕤 ℙ𝕠𝕝𝕝𝕠𝕤 ℍ𝕖𝕣𝕞𝕒𝕟𝕠𝕤',
            stockrecords__partner_sku=u'ṠÖṀЁṪḦЇṄĠ⸚ḊЁḶЇĊЇÖÜṠ',
            stockrecords__price_excl_tax=D('9.99'),
        )

        self.attribute_value = factories.ProductAttributeValueFactory(
            attribute=product_attribute,
            product=pollos_hermanos,
            value_text='pollos/hermanosX/2015'
        )

        self.basket = factories.create_basket(empty=True)
        self.basket.add_product(pollos_hermanos, 1)

        self.order = factories.create_order(
            number=self.ORDER_NUMBER, basket=self.basket, user=user, status=ORDER.BEING_PROCESSED
        )
        # the processor will pass through a string representation of this
        self.order_total = unicode(self.order.total_excl_tax)

        # Remove logger override
        self.addCleanup(logging.disable, logging.NOTSET)


class BasePaymentProcessorTests(PaymentProcessorTestCase):
    """Tests of the base payment processor class."""

    @raises(NotImplementedError)
    def test_base_processor_get_parameters_unusable(self):
        """Test that use of the get_transaction_parameters base payment processor class fails."""
        BasePaymentProcessor().get_transaction_parameters(self.order)

    @raises(NotImplementedError)
    def test_processor_reponse_unusable(self):
        """ Test that we can't use the base processor_response. """
        params = {}
        BasePaymentProcessor().handle_processor_response(params)


class CybersourceTests(PaymentProcessorTestCase):
    """ Abstract test class for Cybersource tests. """

    def test_configuration(self):
        """ Verifies configuration is read from settings. """
        self.assertDictEqual(Cybersource().configuration, settings.PAYMENT_PROCESSOR_CONFIG[Cybersource.NAME])


class CybersourceParameterGenerationTests(CybersourceTests):
    """Tests of the CyberSource processor class related to generating parameters."""
    UUID_HEX = 'madrigal'
    PI_DAY = datetime.datetime(2015, 3, 14, 9, 26, 53)
    RECEIPT_PAGE_URL = CANCEL_PAGE_URL = 'http://www.lospolloshermanos.com'
    MERCHANT_DEFINED_DATA = [u'ℂ𝕙𝕚𝕝𝕖', u'𝕄𝕖𝕩𝕚𝕔𝕠', u'ℕ𝕖𝕨 𝕄𝕖𝕩𝕚𝕔𝕠']

    def setUp(self):
        super(CybersourceParameterGenerationTests, self).setUp()

        uuid_patcher = mock.patch.object(
            processors.uuid.UUID,
            'hex',
            new_callable=mock.PropertyMock(return_value=self.UUID_HEX)
        )
        uuid_patcher.start()
        self.addCleanup(uuid_patcher.stop)

        datetime_patcher = mock.patch.object(
            processors.datetime,
            'datetime',
            mock.Mock(wraps=datetime.datetime)
        )
        mocked_datetime = datetime_patcher.start()
        mocked_datetime.utcnow.return_value = self.PI_DAY
        self.addCleanup(datetime_patcher.stop)

    def test_processor_name(self):
        """Test that the name constant on the processor class is correct."""
        self.assertEqual(Cybersource.NAME, CS.NAME)

    def test_transaction_parameter_generation(self):
        """Test that transaction parameter generation produces the correct output for a test order."""
        self._assert_order_parameters(self.basket)

    def test_override_receipt_and_cancel_pages(self):
        """Test that receipt and cancel page override parameters are included when necessary."""
        self._assert_order_parameters(
            self.basket,
            receipt_page_url=self.RECEIPT_PAGE_URL,
            cancel_page_url=self.CANCEL_PAGE_URL
        )

    def test_merchant_defined_data(self):
        """Test that merchant-defined data parameters are included when necessary."""
        self._assert_order_parameters(
            self.basket,
            merchant_defined_data=self.MERCHANT_DEFINED_DATA
        )

    @raises(UnsupportedProductError)
    def test_receipt_error(self):
        """Test that a single seat CyberSource processor will not construct a receipt for an unknown product. """
        self.product_class.name = 'Not A Seat'
        self.product_class.save()
        self._assert_order_parameters(
            self.basket
        )

    @raises(ExcessiveMerchantDefinedData)
    def test_excessive_merchant_defined_data(self):
        """Test that excessive merchant-defined data is not accepted."""
        # Generate a list of strings with a number of elements exceeding the maximum number
        # of optional fields allowed by CyberSource
        excessive_data = [unicode(i) for i in xrange(CS.MAX_OPTIONAL_FIELDS + 1)]
        SingleSeatCybersource().get_transaction_parameters(self.basket, merchant_defined_data=excessive_data)

    def _assert_order_parameters(self, basket, receipt_page_url=None, cancel_page_url=None, merchant_defined_data=None):
        """Verify that returned transaction parameters match expectations."""

        expected_receipt_page_url = receipt_page_url
        if not receipt_page_url:
            expected_receipt_page_url = '{receipt_url}{course_key}/?payment-order-num={order_number}'.format(
                receipt_url=settings.PAYMENT_PROCESSOR_CONFIG['cybersource']['receipt_page_url'],
                course_key=self.attribute_value.value,
                order_number=self.basket.id
            )

        if not cancel_page_url:
            cancel_page_url = settings.PAYMENT_PROCESSOR_CONFIG['cybersource']['cancel_page_url']

        returned_parameters = SingleSeatCybersource().get_transaction_parameters(
            basket,
            receipt_page_url=receipt_page_url,
            cancel_page_url=cancel_page_url,
            merchant_defined_data=merchant_defined_data
        )

        cybersource_settings = settings.PAYMENT_PROCESSOR_CONFIG[CS.NAME]
        expected_parameters = OrderedDict([
            (CS.FIELD_NAMES.ACCESS_KEY, cybersource_settings['access_key']),
            (CS.FIELD_NAMES.PROFILE_ID, cybersource_settings['profile_id']),
            (CS.FIELD_NAMES.REFERENCE_NUMBER, basket.id),
            (CS.FIELD_NAMES.TRANSACTION_UUID, self.UUID_HEX),
            (CS.FIELD_NAMES.TRANSACTION_TYPE, CS.TRANSACTION_TYPE),
            (CS.FIELD_NAMES.PAYMENT_METHOD, CS.PAYMENT_METHOD),
            (CS.FIELD_NAMES.CURRENCY, basket.currency),
            (CS.FIELD_NAMES.AMOUNT, unicode(basket.total_excl_tax)),
            (CS.FIELD_NAMES.LOCALE, getattr(settings, 'LANGUAGE_CODE')),
        ])

        expected_parameters[CS.FIELD_NAMES.OVERRIDE_CUSTOM_RECEIPT_PAGE] = expected_receipt_page_url

        if cancel_page_url:
            expected_parameters[CS.FIELD_NAMES.OVERRIDE_CUSTOM_CANCEL_PAGE] = cancel_page_url

        if merchant_defined_data:
            for n, data in enumerate(merchant_defined_data, start=1):
                expected_parameters[CS.FIELD_NAMES.MERCHANT_DEFINED_DATA_BASE + unicode(n)] = data

        expected_parameters[CS.FIELD_NAMES.SIGNED_DATE_TIME] = self.PI_DAY.strftime(CS.ISO_8601_FORMAT)

        expected_parameters[CS.FIELD_NAMES.UNSIGNED_FIELD_NAMES] = CS.UNSIGNED_FIELD_NAMES
        expected_parameters[CS.FIELD_NAMES.SIGNED_FIELD_NAMES] = CS.UNSIGNED_FIELD_NAMES
        expected_parameters[CS.FIELD_NAMES.SIGNED_FIELD_NAMES] = CS.SEPARATOR.join(expected_parameters.keys())

        # Generate a comma-separated list of keys and values to be signed. CyberSource refers to this
        # as a 'Version 1' signature in their documentation.
        # pylint: disable=protected-access
        expected_parameters[CS.FIELD_NAMES.SIGNATURE] = SingleSeatCybersource()._generate_signature(expected_parameters)

        self.assertEqual(returned_parameters, expected_parameters)


@override_settings(PAYMENT_PROCESSORS=('ecommerce.extensions.payment.processors.SingleSeatCybersource',))
@ddt.ddt
class CybersourcePaymentAcceptanceTests(CybersourceTests):
    """Tests of the CyberSource processor class related to checking response."""
    FAILED_DECISIONS = ["DECLINE", "CANCEL", "ERROR"]

    def setUp(self):
        super(CybersourcePaymentAcceptanceTests, self).setUp()

    def test_process_payment_success(self):
        """ Test that we processed the params successfully """
        # Simulate a callback from CyberSource indicating that payment was successful
        params = self._signed_callback_params(
            self.order.number, self.order_total, self.order_total, currency=self.order.currency
        )
        result = Cybersource().handle_processor_response(params)

        # Expect that we processed the payment successfully
        self.assertTrue(result[PC.SUCCESS])
        self.assertEqual(result[PC.ORDER_NUMBER], self.order.number)

    def test_process_payment_invalid_signature(self):
        """ Simulate a callback from CyberSource indicating that the payment has an invalid signature """
        params = self._signed_callback_params(
            self.order.number, self.order_total, self.order_total, signature="invalid!", currency=self.order.currency
        )
        result = Cybersource().handle_processor_response(params)

        # Expect that we get an error
        self.assertFalse(result[PC.SUCCESS])

    def test_process_payment_invalid_order(self):
        """ Use an invalid order ID """
        params = self._signed_callback_params(
            "98272", self.order_total, self.order_total, currency=self.order.currency
        )
        result = Cybersource().handle_processor_response(params)

        # Expect an error
        self.assertFalse(result[PC.SUCCESS])

    def test_process_invalid_payment_amount(self):
        """ Change the payment amount (no longer matches the database order record) """
        params = self._signed_callback_params(
            self.order.number, "145.00", "145.00", currency=self.order.currency
        )
        result = Cybersource().handle_processor_response(params)

        # Expect an error
        self.assertFalse(result[PC.SUCCESS])

    def test_process_amount_paid_not_decimal(self):
        """ Change the payment amount to a non-decimal """
        params = self._signed_callback_params(
            self.order.number, self.order_total, "abcd", currency=self.order.currency
        )
        result = Cybersource().handle_processor_response(params)

        # Expect an error
        self.assertFalse(result[PC.SUCCESS])

    def test_process_user_cancelled(self):
        """ Simulate a user cancelling the transaction """
        # set the order status to what we expect after being sent out to CyberSource
        params = self._signed_callback_params(
            self.order.number, self.order_total, self.order_total, currency=self.order.currency, decision=CS.CANCEL
        )
        result = Cybersource().handle_processor_response(params)

        # Expect an error
        self.assertFalse(result[PC.SUCCESS])
        # verify that the order has been updated
        order = Order.objects.get(number=self.order.number)
        self.assertEquals(order.status, ORDER.PAYMENT_CANCELLED)

    def test_process_user_cancelled_invalid_order(self):
        """ Simulate a user cancelling the transaction """
        # set the order status to what we expect after being sent out to CyberSource
        params = self._signed_callback_params(
            'fake', self.order_total, self.order_total, currency=self.order.currency, decision=CS.CANCEL
        )
        result = Cybersource().handle_processor_response(params)

        # Expect an error
        self.assertFalse(result[PC.SUCCESS])

    def test_process_payment_declined(self):
        """ Simulate the processor declining the transaction """
        # set the order status to what we expect after being sent out to CyberSource
        params = self._signed_callback_params(
            self.order.number, self.order_total, self.order_total, currency=self.order.currency, decision=CS.DECLINE
        )
        result = Cybersource().handle_processor_response(params)

        # Expect an error
        self.assertFalse(result[PC.SUCCESS])
        # verify that the order has been updated
        order = Order.objects.get(number=self.order.number)
        self.assertEquals(order.status, ORDER.PAYMENT_ERROR)

    def test_process_payment_declined_invalid_order(self):
        """ Simulate the processor declining a transaction to an invalid order. """
        # set the order status to what we expect after being sent out to CyberSource
        params = self._signed_callback_params(
            'fake', self.order_total, self.order_total, currency=self.order.currency, decision=CS.DECLINE
        )
        result = Cybersource().handle_processor_response(params)

        # Expect an error
        self.assertFalse(result[PC.SUCCESS])

    def test_process_no_credit_card_digits(self):
        """ Simulate a credit card number with no digits provided """
        params = self._signed_callback_params(
            self.order.number, self.order_total, self.order_total,
            card_number='nodigits', currency=self.order.currency
        )
        result = Cybersource().handle_processor_response(params)

        # Expect that we processed the payment successfully
        self.assertTrue(
            result[PC.SUCCESS],
        )

    @ddt.data('req_reference_number', 'req_currency', 'decision', 'auth_amount')
    def test_process_missing_parameters(self, missing_param):
        """ Test removing a required parameter """
        params = self._signed_callback_params(
            self.order.number, self.order_total, self.order_total, currency=self.order.currency
        )
        del params[missing_param]

        # Recalculate the signature with no signed fields so we can get past
        # signature validation.
        params[CS.FIELD_NAMES.SIGNED_FIELD_NAMES] = 'reason_code,message'
        # pylint: disable=protected-access
        params[CS.FIELD_NAMES.SIGNATURE] = Cybersource()._generate_signature(params)

        result = Cybersource().handle_processor_response(params)

        # Expect an error
        self.assertFalse(result[PC.SUCCESS])

    def test_process_error_parameters(self):
        """ Test when CyberSource returns an ERROR decision, the order status is updated. """
        params = self._signed_callback_params(
            self.order.number, self.order_total, self.order_total, currency=self.order.currency, decision=CS.ERROR
        )
        result = Cybersource().handle_processor_response(params)
        self.assertFalse(result[PC.SUCCESS])
        order = Order.objects.get(number=self.order.number)
        self.assertEquals(order.status, ORDER.PAYMENT_ERROR)

    def _signed_callback_params(
            self, order_id, order_amount, paid_amount,
            decision=CS.ACCEPT, signature=None, card_number='xxxxxxxxxxxx1111',
            first_name='John', currency='usd',
    ):
        """
        Construct parameters that could be returned from CyberSource
        to our payment callback.

        Some values can be overridden to simulate different test scenarios,
        but most are fake values captured from interactions with
        a CyberSource test account.

        Args:
            order_id (string or int): The ID of the `Order` model.
            order_amount (string): The cost of the order.
            paid_amount (string): The amount the user paid using CyberSource.

        Keyword Args:

            decision (string): Whether the payment was accepted or rejected or declined.
            signature (string): If provided, use this value instead of calculating the signature.
            card_numer (string): If provided, use this value instead of the default credit card number.
            first_name (string): If provided, the first name of the user.

        Returns:
            dict

        """
        # Parameters sent from CyberSource to our callback implementation
        # These were captured from the CC test server.

        signed_field_names = ['transaction_id',
                              'decision',
                              'req_access_key',
                              'req_profile_id',
                              'req_transaction_uuid',
                              'req_transaction_type',
                              'req_reference_number',
                              'req_amount',
                              'req_currency',
                              'req_locale',
                              'req_payment_method',
                              'req_override_custom_receipt_page',
                              'req_bill_to_forename',
                              'req_bill_to_surname',
                              'req_bill_to_email',
                              'req_bill_to_address_line1',
                              'req_bill_to_address_city',
                              'req_bill_to_address_state',
                              'req_bill_to_address_country',
                              'req_bill_to_address_postal_code',
                              'req_card_number',
                              'req_card_type',
                              'req_card_expiry_date',
                              'message',
                              'reason_code',
                              'auth_avs_code',
                              'auth_avs_code_raw',
                              'auth_response',
                              'auth_amount',
                              'auth_code',
                              'auth_trans_ref_no',
                              'auth_time',
                              'bill_trans_ref_no',
                              'signed_field_names',
                              'signed_date_time']

        # if decision is in FAILED_DECISIONS list then remove  auth_amount from
        # signed_field_names list.
        if decision in self.FAILED_DECISIONS:
            signed_field_names.remove(CS.FIELD_NAMES.AUTH_AMOUNT)

        params = {
            # Parameters that change based on the test
            'decision': decision,
            'req_reference_number': order_id,
            'req_amount': order_amount,
            'auth_amount': paid_amount,
            'req_card_number': card_number,
            'req_currency': currency,
            'req_bill_to_forename': first_name,

            # Stub values
            'utf8': u'✓',
            'req_bill_to_address_country': 'US',
            'auth_avs_code': 'X',
            'req_card_expiry_date': '01-2018',
            'bill_trans_ref_no': '85080648RYI23S6I',
            'req_bill_to_address_state': 'MA',
            'signed_field_names': ','.join(signed_field_names),
            'req_payment_method': 'card',
            'req_transaction_type': 'sale',
            'auth_code': '888888',
            'req_locale': 'en',
            'reason_code': '100',
            'req_bill_to_address_postal_code': '02139',
            'req_bill_to_address_line1': '123 Fake Street',
            'req_card_type': '001',
            'req_bill_to_address_city': 'Boston',
            'signed_date_time': '2014-08-18T14:07:10Z',
            'auth_avs_code_raw': 'I1',
            'transaction_id': '4083708299660176195663',
            'auth_time': '2014-08-18T140710Z',
            'message': 'Request was processed successfully.',
            'auth_response': '100',
            'req_profile_id': '0000001',
            'req_transaction_uuid': 'ddd9935b82dd403f9aa4ba6ecf021b1f',
            'auth_trans_ref_no': '85080648RYI23S6I',
            'req_bill_to_surname': 'Doe',
            'req_bill_to_email': 'john@example.com',
            'req_override_custom_receipt_page': 'http://localhost:8000/shoppingcart/postpay_callback/',
            'req_access_key': 'abcd12345',
        }

        # if decision is in FAILED_DECISIONS list then remove the auth_amount from params dict

        if decision in self.FAILED_DECISIONS:
            del params[CS.FIELD_NAMES.AUTH_AMOUNT]

        # Calculate the signature
        # pylint: disable=protected-access
        generated_signature = Cybersource()._generate_signature(params)
        params[CS.FIELD_NAMES.SIGNATURE] = signature if signature is not None else generated_signature
        return params
