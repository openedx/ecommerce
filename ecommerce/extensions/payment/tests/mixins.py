from __future__ import unicode_literals

import datetime
import logging
import os
from decimal import Decimal
from urlparse import urljoin

import ddt
import mock
import responses
from django.conf import settings
from django.core.urlresolvers import reverse
from factory.django import mute_signals
from oscar.apps.order.exceptions import UnableToPlaceOrder
from oscar.apps.payment.exceptions import PaymentError, TransactionDeclined, UserCancelled
from oscar.core.loading import get_class, get_model
from oscar.test import factories, newfactories
from oscar.test.contextmanagers import mock_signal_receiver
from testfixtures import LogCapture

from ecommerce.core.constants import ISO_8601_FORMAT
from ecommerce.extensions.checkout.utils import get_receipt_page_url
from ecommerce.extensions.fulfillment.status import ORDER
from ecommerce.extensions.payment.constants import CARD_TYPES
from ecommerce.extensions.payment.helpers import sign
from ecommerce.extensions.payment.processors.cybersource import Cybersource

CURRENCY = 'USD'
Basket = get_model('basket', 'Basket')
Order = get_model('order', 'Order')
PaymentEventType = get_model('order', 'PaymentEventType')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')
SourceType = get_model('payment', 'SourceType')

logger = logging.getLogger(__name__)
post_checkout = get_class('checkout.signals', 'post_checkout')


class PaymentEventsMixin(object):
    def get_order(self, basket):
        """ Return the order associated with a basket. """
        return Order.objects.get(basket=basket)

    def assert_processor_response_recorded(self, processor_name, transaction_id, response, basket=None):
        """ Ensures a PaymentProcessorResponse exists for the corresponding processor and response. """
        ppr = PaymentProcessorResponse.objects.filter(
            processor_name=processor_name,
            transaction_id=transaction_id
        ).latest('created')
        self.assertEqual(ppr.response, response)
        self.assertEqual(ppr.basket, basket)

        return ppr.id

    def assert_valid_payment_event_fields(self, payment_event, amount, payment_event_type, processor_name, reference):
        """ Ensures the given PaymentEvent's fields match the specified values. """
        self.assertEqual(payment_event.amount, amount)
        self.assertEqual(payment_event.event_type, payment_event_type)
        self.assertEqual(payment_event.reference, reference)
        self.assertEqual(payment_event.processor_name, processor_name)

    def assert_payment_event_exists(self, basket, payment_event_type, reference, processor_name):
        """ Validates that a single PaymentEvent exists for the basket's associated order. """
        order = self.get_order(basket)
        self.assertEqual(order.payment_events.count(), 1)

        payment_event = order.payment_events.first()
        amount = basket.total_incl_tax
        self.assert_valid_payment_event_fields(payment_event, amount, payment_event_type, processor_name, reference)

    def assert_basket_matches_source(self, basket, source, source_type, reference, label, card_type=None):
        """
        Validates that the Source has the correct SourceType and that currency and amounts match the given Basket.
        """
        total = basket.total_incl_tax
        self.assertEqual(source.source_type, source_type)
        self.assertEqual(source.currency, basket.currency)
        self.assertEqual(source.amount_allocated, total)
        self.assertEqual(source.amount_debited, total)
        self.assertEqual(source.reference, reference)
        self.assertEqual(source.label, label)

        if card_type:
            self.assertEqual(source.card_type, card_type)

    def assert_payment_source_exists(self, basket, source_type, reference, label):
        """ Validates that a single Source exists for the basket's associated order. """
        order = self.get_order(basket)
        self.assertEqual(order.sources.count(), 1)

        source = order.sources.first()
        self.assert_basket_matches_source(basket, source, source_type, reference, label)


class CybersourceMixin(PaymentEventsMixin):
    """ Mixin with helper methods for testing CyberSource notifications. """
    DEFAULT_CARD_TYPE = 'visa'

    def _assert_payment_data_recorded(self, notification):
        """ Ensure PaymentEvent, PaymentProcessorResponse, and Source objects are created for the basket. """

        # Ensure the response is stored in the database
        self.assert_processor_response_recorded(self.processor_name, notification['transaction_id'], notification,
                                                basket=self.basket)

        # Validate a payment Source was created
        reference = notification['transaction_id']
        source_type = SourceType.objects.get(code=self.processor_name)
        label = notification['req_card_number']
        self.assert_payment_source_exists(self.basket, source_type, reference, label)

        # Validate that PaymentEvents exist
        paid_type = PaymentEventType.objects.get(code='paid')
        self.assert_payment_event_exists(self.basket, paid_type, reference, self.processor_name)

    def _assert_processing_failure(self, notification, error_message, log_level='ERROR'):
        """Verify that payment processing operations fail gracefully."""
        logger_name = 'ecommerce.extensions.payment.views.cybersource'
        with LogCapture(logger_name) as l:
            self.client.post(self.path, notification)

            ppr_id = self.assert_processor_response_recorded(
                self.processor_name,
                notification['transaction_id'],
                notification,
                basket=self.basket
            )

            error_message = error_message.format(basket_id=self.basket.id, response_id=ppr_id)

            l.check(
                (
                    logger_name,
                    'INFO',
                    'Received CyberSource payment notification for transaction [{transaction_id}], '
                    'associated with basket [{basket_id}].'.format(
                        transaction_id=notification['transaction_id'],
                        basket_id=self.basket.id
                    )
                ),
                (logger_name, log_level, error_message)
            )

    def generate_signature(self, secret_key, data):
        """ Generate a signature for the given data dict. """
        keys = data['signed_field_names'].split(',')

        message = ','.join(['{key}={value}'.format(key=key, value=data[key]) for key in keys])
        return sign(message, secret_key)

    def make_billing_address(self, overrides=None):
        """
        Create a billing address for Cybersource tests with minimal required
        fields defined.
        """
        kwargs = {
            'first_name': 'TestForename',
            'last_name': 'TestSurname',
            'line1': 'TestLine1',
            'line2': '',  # this is not required by Cybersource, so make it empty unless the caller overrides it.
            'line4': 'TestLine4',
            'postcode': 'TestPostCode',
            'country': newfactories.CountryFactory(),
        }
        kwargs.update(overrides or {})
        return newfactories.BillingAddressFactory(**kwargs)

    def generate_notification(self, basket, decision='ACCEPT', billing_address=None, auth_amount=None, **kwargs):
        """
        Generates a dict containing the API reply fields expected to be received
        from CyberSource.
        """
        reason_code = kwargs.get('reason_code', '100')
        req_reference_number = kwargs.get('req_reference_number', basket.order_number)
        total = unicode(basket.total_incl_tax)
        auth_amount = auth_amount or total

        notification = {
            'decision': decision,
            'reason_code': reason_code,
            'req_reference_number': req_reference_number,
            'transaction_id': '123456',
            'auth_amount': auth_amount,
            'req_amount': total,
            'req_tax_amount': '0.00',
            'req_currency': basket.currency,
            'req_card_number': 'xxxxxxxxxxxx1111',
            'req_card_type': CARD_TYPES[self.DEFAULT_CARD_TYPE]['cybersource_code'],
            'req_profile_id': self.processor.profile_id,
        }

        if billing_address:
            notification.update({
                'req_bill_to_forename': billing_address.first_name,
                'req_bill_to_surname': billing_address.last_name,
                'req_bill_to_address_line1': billing_address.line1,
                'req_bill_to_address_city': billing_address.line4,
                'req_bill_to_address_postal_code': billing_address.postcode,
                'req_bill_to_address_country': billing_address.country.iso_3166_1_a2
            })

            # handle optional address fields
            if billing_address.line2:
                notification['req_bill_to_address_line2'] = billing_address.line2
            if billing_address.state:
                notification['req_bill_to_address_state'] = billing_address.state

        notification['signed_field_names'] = ','.join(notification.keys())
        notification['signature'] = self.generate_signature(self.processor.secret_key, notification)
        return notification

    def mock_cybersource_wsdl(self):
        files = ('CyberSourceTransaction_1.115.wsdl', 'CyberSourceTransaction_1.115.xsd')

        for filename in files:
            path = os.path.join(os.path.dirname(__file__), filename)
            body = open(path, 'r').read()
            url = urljoin(settings.PAYMENT_PROCESSOR_CONFIG['edx']['cybersource']['soap_api_url'], filename)
            responses.add(responses.GET, url, body=body)

    # pylint:disable=bad-continuation
    def mock_refund_response(self, amount=Decimal(100), currency=CURRENCY, transaction_id=None, basket_id=None,
                             decision='ACCEPT'):
        url = 'https://ics2wstest.ic3.com/commerce/1.x/transactionProcessor'
        body = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
    <soap:Header>
        <wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
            <wsu:Timestamp
                    xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"
                    wsu:Id="Timestamp-1924306294">
                <wsu:Created>2017-06-12T23:40:14.087Z</wsu:Created>
            </wsu:Timestamp>
        </wsse:Security>
    </soap:Header>
    <soap:Body>
        <c:replyMessage xmlns:c="urn:schemas-cybersource-com:transaction-data-1.115">
            <c:merchantReferenceCode>{merchant_reference_code}</c:merchantReferenceCode>
            <c:requestID>{request_id}</c:requestID>
            <c:decision>{decision}</c:decision>
            <c:reasonCode>100</c:reasonCode>
            <c:requestToken>
                Ahj/7wSTDZe9UHPSiXlfKhbFg1ctWLRiycM0uKt0DswBS4q3QiEdIHTiDf3DJpJlukB2NEECcmGy8oWwa2X5HSAA4Tz2
            </c:requestToken>
            <c:purchaseTotals>
                <c:currency>{currency}</c:currency>
            </c:purchaseTotals>
            <c:ccCreditReply>
                <c:reasonCode>100</c:reasonCode>
                <c:requestDateTime>2017-06-12T23:40:14Z</c:requestDateTime>
                <c:amount>{amount}</c:amount>
                <c:reconciliationID>10595141283</c:reconciliationID>
            </c:ccCreditReply>
        </c:replyMessage>
    </soap:Body>
</soap:Envelope>""".format(
            merchant_reference_code=basket_id,
            request_id=transaction_id,
            decision=decision,
            currency=currency,
            amount=str(amount)
        )

        responses.add(responses.POST, url, body=body, content_type='text/xml')

        return body

    def get_expected_transaction_parameters(self, basket, transaction_uuid, include_level_2_3_details=True,
                                            processor=None, use_sop_profile=False, **kwargs):
        """
        Builds expected transaction parameters dictionary.

        Note:
            Callers should separately validate the transaction_uuid parameter to ensure it is a valid UUID.
        """
        processor = processor or Cybersource(self.site)
        configuration = settings.PAYMENT_PROCESSOR_CONFIG['edx'][processor.NAME]
        access_key = configuration['sop_access_key'] if use_sop_profile else configuration['access_key']
        profile_id = configuration['sop_profile_id'] if use_sop_profile else configuration['profile_id']
        secret_key = configuration['sop_secret_key'] if use_sop_profile else configuration['secret_key']

        expected = {
            'access_key': access_key,
            'profile_id': profile_id,
            'transaction_uuid': transaction_uuid,
            'signed_field_names': '',
            'unsigned_field_names': '',
            'signed_date_time': datetime.datetime.utcnow().strftime(ISO_8601_FORMAT),
            'locale': settings.LANGUAGE_CODE,
            'transaction_type': 'sale',
            'reference_number': basket.order_number,
            'amount': unicode(basket.total_incl_tax),
            'currency': basket.currency,
            'override_custom_receipt_page': basket.site.siteconfiguration.build_ecommerce_url(
                reverse('cybersource:redirect')
            ),
            'override_custom_cancel_page': processor.cancel_page_url,
        }

        if include_level_2_3_details:
            expected.update({
                'line_item_count': basket.lines.count(),
                'amex_data_taa1': basket.site.name,
                'purchasing_level': '3',
                'user_po': 'BLANK',
            })

            for index, line in enumerate(basket.lines.all()):
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

        if not use_sop_profile:
            expected['consumer_id'] = basket.owner.username

        # Add the extra parameters
        expected.update(kwargs.get('extra_parameters', {}))

        # Generate a signature
        expected['signed_field_names'] = ','.join(sorted(expected.keys()))
        expected['signature'] = self.generate_signature(secret_key, expected)

        return expected

    def mock_authorization_response(self, accepted=True):
        decision = 'ACCEPT' if accepted else 'REJECTED'
        reason_code = 100 if accepted else 102
        url = 'https://ics2wstest.ic3.com/commerce/1.x/transactionProcessor'
        body = """<?xml version="1.0" encoding="utf-8"?>
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
            <soap:Header>
                <wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
                    <wsu:Timestamp
                            xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"
                            wsu:Id="Timestamp-2033980704">
                        <wsu:Created>2017-07-09T20:42:17.984Z</wsu:Created>
                    </wsu:Timestamp>
                </wsse:Security>
            </soap:Header>
            <soap:Body>
                <c:replyMessage xmlns:c="urn:schemas-cybersource-com:transaction-data-1.115">
                    <c:merchantReferenceCode>EDX-100045</c:merchantReferenceCode>
                    <c:requestID>4996329373316728804010</c:requestID>
                    <c:decision>{decision}</c:decision>
                    <c:reasonCode>{reason_code}</c:reasonCode>
                    <c:requestToken>
                        Ahj//wSTDtn/tVgRrNKqKhbFg0cuWjFgyYNkuHIlfeUBS4ciV95dIHTVjgtDJpJlukB2NEAYMZMO2f+1WBGs0qoAqQu/
                    </c:requestToken>
                    <c:purchaseTotals>
                        <c:currency>USD</c:currency>
                    </c:purchaseTotals>
                    <c:ccAuthReply>
                        <c:reasonCode>{reason_code}</c:reasonCode>
                        <c:amount>99.00</c:amount>
                        <c:authorizationCode>831000</c:authorizationCode>
                        <c:avsCode>Y</c:avsCode>
                        <c:avsCodeRaw>Y</c:avsCodeRaw>
                        <c:authorizedDateTime>2017-07-09T20:42:17Z</c:authorizedDateTime>
                        <c:processorResponse>000</c:processorResponse>
                        <c:paymentNetworkTransactionID>558196000003814</c:paymentNetworkTransactionID>
                        <c:cardCategory>A</c:cardCategory>
                    </c:ccAuthReply>
                    <c:ccCaptureReply>
                        <c:reasonCode>{reason_code}</c:reasonCode>
                        <c:requestDateTime>2017-07-09T20:42:17Z</c:requestDateTime>
                        <c:amount>99.00</c:amount>
                        <c:reconciliationID>10499410206</c:reconciliationID>
                    </c:ccCaptureReply>
                </c:replyMessage>
            </soap:Body>
        </soap:Envelope>
        """.format(
            decision=decision,
            reason_code=reason_code,
        )

        responses.add(responses.POST, url, body=body, content_type='text/xml')

        return body


@ddt.ddt
class CybersourceNotificationTestsMixin(CybersourceMixin):
    """ Mixin with test methods for testing CyberSource payment views. """

    def setUp(self):
        super(CybersourceNotificationTestsMixin, self).setUp()

        self.user = factories.UserFactory()
        self.billing_address = self.make_billing_address()

        self.basket = factories.create_basket()
        self.basket.owner = self.user
        self.basket.site = self.site
        self.basket.freeze()

        self.processor = Cybersource(self.site)
        self.processor_name = self.processor.NAME

    # Disable the normal signal receivers so that we can verify the state of the created order.
    @mute_signals(post_checkout)
    def test_accepted(self):
        """
        When payment is accepted, the following should occur:
            1. The response is recorded and PaymentEvent/Source objects created.
            2. An order for the corresponding basket is created.
            3. The order is fulfilled.
        """

        # The basket should not have an associated order if no payment was made.
        self.assertFalse(Order.objects.filter(basket=self.basket).exists())

        notification = self.generate_notification(self.basket, billing_address=self.billing_address)

        with mock_signal_receiver(post_checkout) as receiver:
            self.client.post(self.path, notification)

            # Validate that a new order exists in the correct state
            order = Order.objects.get(basket=self.basket)
            self.assertIsNotNone(order, 'No order was created for the basket after payment.')
            self.assertEqual(order.status, ORDER.OPEN)

            # Validate the order's line items
            self.assertListEqual(list(order.lines.values_list('product__id', flat=True)),
                                 list(self.basket.lines.values_list('product__id', flat=True)))

            # Verify the post_checkout signal was emitted
            self.assertEqual(receiver.call_count, 1)
            __, kwargs = receiver.call_args
            self.assertEqual(kwargs['order'], order)

        # Validate the payment data was recorded for auditing
        self._assert_payment_data_recorded(notification)

        # The basket should be marked as submitted. Refresh with data from the database.
        basket = Basket.objects.get(id=self.basket.id)
        self.assertTrue(basket.is_submitted)
        self.assertIsNotNone(basket.date_submitted)

    @ddt.data('CANCEL', 'DECLINE', 'ERROR', 'blah!')
    def test_not_accepted(self, decision):
        """
        When payment is NOT accepted, the processor's response should be saved to the database. An order should NOT
        be created.
        """

        notification = self.generate_notification(self.basket, decision=decision)
        self.client.post(self.path, notification)

        # The basket should not have an associated order if no payment was made.
        self.assertFalse(Order.objects.filter(basket=self.basket).exists())

        # Ensure the response is stored in the database
        self.assert_processor_response_recorded(
            self.processor_name,
            notification[u'transaction_id'],
            notification,
            basket=self.basket
        )

    @ddt.data(
        (PaymentError, 'ERROR', 'CyberSource payment failed for basket [{basket_id}]. '
                                'The payment response was recorded in entry [{response_id}].'),
        (UserCancelled, 'INFO', 'CyberSource payment did not complete for basket [{basket_id}] because '
                                '[UserCancelled]. The payment response was recorded in entry [{response_id}].'),
        (TransactionDeclined, 'INFO', 'CyberSource payment did not complete for basket [{basket_id}] because '
                                      '[TransactionDeclined]. The payment response was recorded in entry '
                                      '[{response_id}].'),
        (KeyError, 'ERROR', 'Attempts to handle payment for basket [{basket_id}] failed.')
    )
    @ddt.unpack
    def test_payment_handling_error(self, error_class, log_level, error_message):
        """
        Verify that CyberSource's merchant notification is saved to the database despite an error handling payment.
        """
        notification = self.generate_notification(
            self.basket,
            billing_address=self.billing_address,
        )
        with mock.patch.object(self.view, 'handle_payment', side_effect=error_class) as fake_handle_payment:
            self._assert_processing_failure(
                notification,
                error_message,
                log_level
            )
            self.assertTrue(fake_handle_payment.called)

    @ddt.data(UnableToPlaceOrder, KeyError)
    def test_unable_to_place_order(self, exception):
        """ When payment is accepted, but an order cannot be placed, log an error and return HTTP 200. """

        notification = self.generate_notification(
            self.basket,
            billing_address=self.billing_address,
        )

        # Verify that anticipated errors are handled gracefully.
        with mock.patch.object(
            self.view,
            'handle_order_placement',
            side_effect=exception
        ) as fake_handle_order_placement:
            error_message = 'Payment was received, but an order for basket [{basket_id}] could not be placed.'.format(
                basket_id=self.basket.id,
            )
            self._assert_processing_failure(notification, error_message)
            self.assertTrue(fake_handle_order_placement.called)

    def test_invalid_basket(self):
        """ When payment is accepted for a non-existent basket, log an error and record the response. """
        order_number = '{}-{}'.format(self.partner.short_code.upper(), 101986)

        notification = self.generate_notification(
            self.basket,
            billing_address=self.billing_address,
            req_reference_number=order_number,
        )
        self.client.post(self.path, notification)

        self.assert_processor_response_recorded(self.processor_name, notification['transaction_id'], notification)

    @ddt.data(Basket.MERGED, Basket.SAVED, Basket.OPEN, Basket.SUBMITTED)
    def test_invalid_basket_status(self, status):
        """ An error should be raised if the basket is in a non-frozen state. """
        self.basket.status = status
        self.basket.save()
        notification = self.generate_notification(self.basket, billing_address=self.billing_address)
        msg = (
            'Received CyberSource payment notification for basket [{id}] '
            'which is in a non-frozen state, [{status}]'
        ).format(
            id=self.basket.id,
            status=status
        )

        self._assert_processing_failure(notification, msg, 'INFO')

    @ddt.data(('line2', 'foo'), ('state', 'bar'))
    @ddt.unpack
    def test_optional_fields(self, field_name, field_value, ):
        """ Ensure notifications are handled properly with or without keys/values present for optional fields. """

        with mock.patch(
            'ecommerce.extensions.payment.views.cybersource.{}.handle_order_placement'.format(self.view.__name__)
        ) as mock_placement_handler:
            def check_notification_address(notification, expected_address):
                self.client.post(self.path, notification)
                self.assertTrue(mock_placement_handler.called)
                actual_address = mock_placement_handler.call_args[0][6]
                self.assertEqual(actual_address.summary, expected_address.summary)

            cybersource_key = 'req_bill_to_address_{}'.format(field_name)

            # Generate a notification without the optional field set.
            # Ensure that the Cybersource key does not exist in the notification,
            # and that the address our endpoint parses from the notification is
            # equivalent to the original.
            notification = self.generate_notification(
                self.basket,
                billing_address=self.billing_address,
            )
            self.assertNotIn(cybersource_key, notification)
            check_notification_address(notification, self.billing_address)

            # Add the optional field to the billing address in the notification.
            # Ensure that the Cybersource key now does exist, and that our endpoint
            # recognizes and parses it correctly.
            billing_address = self.make_billing_address({field_name: field_value})
            notification = self.generate_notification(
                self.basket,
                billing_address=billing_address,
            )
            self.assertIn(cybersource_key, notification)
            check_notification_address(notification, billing_address)

    def test_invalid_signature(self):
        """
        If the response signature is invalid, the view should return a 400. The response should be recorded, but an
        order should NOT be created.
        """
        notification = self.generate_notification(self.basket)
        notification['signature'] = 'Tampered'
        self.client.post(self.path, notification)

        # The basket should not have an associated order
        self.assertFalse(Order.objects.filter(basket=self.basket).exists())

        # The response should be saved.
        self.assert_processor_response_recorded(self.processor_name, notification['transaction_id'], notification,
                                                basket=self.basket)

    def test_duplicate_reference_code(self):
        """
        Verify that if CyberSource declines to charge for an existing order, we
        redirect to the receipt page for the existing order.
        """
        notification = self.generate_notification(self.basket, billing_address=self.billing_address)

        self.client.post(self.path, notification)

        # Validate that a new order exists in the correct state
        order = Order.objects.get(basket=self.basket)
        self.assertIsNotNone(order, 'No order was created for the basket after payment.')

        # Mutate the notification and re-use it to simulate a duplicate reference
        # number error from CyberSource.
        notification.update({
            'decision': 'ERROR',
            'reason_code': '104',
        })

        # Re-sign the response. This is necessary because we've tampered with fields
        # that have already been signed.
        notification['signature'] = self.generate_signature(self.processor.secret_key, notification)

        response = self.client.post(self.path, notification)

        expected_redirect = get_receipt_page_url(
            self.site.siteconfiguration,
            order_number=notification.get('req_reference_number')
        )

        self.assertRedirects(response, expected_redirect, fetch_redirect_response=False)


class PaypalMixin(object):
    """Mixin with helper methods for mocking PayPal API responses."""
    APPROVAL_URL = 'https://api.sandbox.paypal.com/fake-approval-url'
    EMAIL = 'test-buyer@paypal.com'
    PAYER_ID = 'PAYERID'
    PAYMENT_ID = 'PAY-123ABC'
    PAYMENT_CREATION_STATE = 'created'
    PAYMENT_EXECUTION_STATE = 'approved'
    PAYER_INFO = {
        'email': EMAIL,
        'first_name': 'test',
        'last_name': 'buyer',
        'payer_id': '123ABC',
        'shipping_address': {
            'city': 'San Jose',
            'country_code': 'US',
            'line1': '1 Main St',
            'postal_code': '95131',
            'recipient_name': 'test buyer',
            'state': 'CA'
        }
    }
    RETURN_DATA = {
        'paymentId': PAYMENT_ID,
        'PayerID': PAYER_ID
    }
    SALE_ID = '789XYZ'

    def mock_api_response(self, path, body, method=responses.POST, status=200, rsps=responses):
        url = self._create_api_url(path)
        rsps.add(method, url, status=status, json=body)

    def mock_oauth2_response(self, rsps=responses):
        oauth2_response = {
            'scope': 'https://api.paypal.com/v1/payments/.*',
            'access_token': 'fake-access-token',
            'token_type': 'Bearer',
            'app_id': 'APP-123ABC',
            'expires_in': 28800
        }

        self.mock_api_response('/v1/oauth2/token', oauth2_response, rsps=rsps)

    def get_payment_creation_response_mock(self, basket, state=PAYMENT_CREATION_STATE, approval_url=APPROVAL_URL):
        total = unicode(basket.total_incl_tax)
        payment_creation_response = {
            'create_time': '2015-05-04T18:18:27Z',
            'id': self.PAYMENT_ID,
            'intent': 'sale',
            'links': [
                {
                    'href': 'https://api.sandbox.paypal.com/v1/payments/payment/{}'.format(self.PAYMENT_ID),
                    'method': 'GET',
                    'rel': 'self'
                },
                {
                    'href': 'https://api.sandbox.paypal.com/v1/payments/payment/{}/execute'.format(self.PAYMENT_ID),
                    'method': 'POST',
                    'rel': 'execute'
                }
            ],
            'payer': {
                'payer_info': {'shipping_address': {}},
                'payment_method': 'paypal'
            },
            'redirect_urls': {
                'cancel_url': 'http://fake-cancel-page',
                'return_url': 'http://fake-return-url'
            },
            'state': state,
            'transactions': [{
                'amount': {
                    'currency': CURRENCY,
                    'details': {'subtotal': total},
                    'total': total
                },
                'item_list': {
                    'items': [
                        {
                            'quantity': line.quantity,
                            'name': line.product.title,
                            'price': unicode(line.line_price_incl_tax_incl_discounts / line.quantity),
                            'currency': line.stockrecord.price_currency,
                        }
                        for line in basket.all_lines()
                    ],
                },
                'invoice_number': basket.order_number,
                'related_resources': []
            }],
            'update_time': '2015-05-04T18:18:27Z'
        }

        if approval_url:
            payment_creation_response['links'].append({
                'href': approval_url,
                'method': 'REDIRECT',
                'rel': 'approval_url'
            })
        return payment_creation_response

    def mock_payment_creation_response(self, basket, state=PAYMENT_CREATION_STATE, approval_url=APPROVAL_URL,
                                       find=False):
        payment_creation_response = self.get_payment_creation_response_mock(basket, state, approval_url)

        if find:
            path = '/v1/payments/payment/{}'.format(self.PAYMENT_ID)
            self.mock_api_response(path, payment_creation_response, method=responses.GET)
        else:
            self.mock_api_response('/v1/payments/payment', payment_creation_response)

        return payment_creation_response

    def get_payment_creation_error_response_mock(self):
        payment_creation_error_response = {
            u'error': {
                'debug_id': '23432',
                'message': '500 server error'
            },
            u'intent': u'sale',
            u'payer': {
                u'payer_info': {u'shipping_address': {}},
                u'payment_method': u'paypal'
            },
            u'redirect_urls': {
                u'cancel_url': u'http://fake-cancel-page',
                u'return_url': u'http://fake-return-url'
            },
            u'state': 'failed',
            u'transactions': []
        }
        return payment_creation_error_response

    def mock_payment_execution_response(self, basket, state=PAYMENT_EXECUTION_STATE, payer_info=None):
        if payer_info is None:
            payer_info = self.PAYER_INFO
        total = unicode(basket.total_incl_tax)
        payment_execution_response = {
            'create_time': '2015-05-04T15:55:27Z',
            'id': self.PAYMENT_ID,
            'intent': 'sale',
            'links': [{
                'href': 'https://api.sandbox.paypal.com/v1/payments/payment/{}'.format(self.PAYMENT_ID),
                'method': 'GET',
                'rel': 'self'
            }],
            'payer': {
                'payer_info': payer_info,
                'payment_method': 'paypal'
            },
            'redirect_urls': {
                'cancel_url': 'http://fake-cancel-page',
                'return_url': 'http://fake-return-url'
            },
            'state': state,
            'transactions': [{
                'amount': {
                    'currency': CURRENCY,
                    'details': {'subtotal': total},
                    'total': total
                },
                'item_list': {
                    'items': [
                        {
                            'quantity': line.quantity,
                            'name': line.product.title,
                            'price': unicode(line.line_price_incl_tax_incl_discounts / line.quantity),
                            'currency': line.stockrecord.price_currency,
                        }
                        for line in basket.all_lines()
                    ],
                },
                'invoice_number': basket.order_number,
                'related_resources': [{
                    'sale': {
                        'amount': {
                            'currency': CURRENCY,
                            'total': total
                        },
                        'create_time': '2015-05-04T15:55:27Z',
                        'id': self.SALE_ID,
                        'links': [
                            {
                                'href': 'https://api.sandbox.paypal.com/v1/payments/sale/{}'.format(self.SALE_ID),
                                'method': 'GET',
                                'rel': 'self'
                            },
                            {
                                'href': 'https://api.sandbox.paypal.com/v1/payments/sale/{}/refund'.format(
                                    self.SALE_ID
                                ),
                                'method': 'POST',
                                'rel': 'refund'
                            },
                            {
                                'href': 'https://api.sandbox.paypal.com/v1/payments/payment/{}'.format(
                                    self.PAYMENT_ID
                                ),
                                'method': 'GET',
                                'rel': 'parent_payment'
                            }
                        ],
                        'parent_payment': self.PAYMENT_ID,
                        'payment_mode': 'INSTANT_TRANSFER',
                        'protection_eligibility': 'ELIGIBLE',
                        'protection_eligibility_type': 'ITEM_NOT_RECEIVED_ELIGIBLE,UNAUTHORIZED_PAYMENT_ELIGIBLE',
                        'state': 'completed',
                        'transaction_fee': {
                            'currency': CURRENCY,
                            'value': '0.50'
                        },
                        'update_time': '2015-05-04T15:58:47Z'
                    }
                }]
            }],
            'update_time': '2015-05-04T15:58:47Z'
        }

        self.mock_api_response(
            '/v1/payments/payment/{}/execute'.format(self.PAYMENT_ID),
            payment_execution_response
        )

        return payment_execution_response

    def _create_api_url(self, path):
        mode = settings.PAYMENT_PROCESSOR_CONFIG['edx']['paypal']['mode']
        root = 'https://api.sandbox.paypal.com' if mode == 'sandbox' else 'https://api.paypal.com'

        return urljoin(root, path)
