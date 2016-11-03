from __future__ import unicode_literals

import datetime
import json
import os
from urlparse import urljoin

import httpretty
import mock
from django.conf import settings
from oscar.core.loading import get_model
from oscar.test import newfactories
from suds.sudsobject import Factory

from ecommerce.core.constants import ISO_8601_FORMAT
from ecommerce.extensions.checkout.utils import get_receipt_page_url
from ecommerce.extensions.payment.constants import CARD_TYPES
from ecommerce.extensions.payment.helpers import sign
from ecommerce.extensions.payment.processors.cybersource import Cybersource

CURRENCY = 'USD'
Order = get_model('order', 'Order')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')


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


class CybersourceMixin(object):
    """ Mixin with helper methods for testing CyberSource notifications. """
    DEFAULT_CARD_TYPE = 'visa'

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
        """ Generates a dict containing the API reply fields expected to be received from CyberSource. """

        req_reference_number = kwargs.get('req_reference_number', basket.order_number)
        total = unicode(basket.total_incl_tax)
        auth_amount = auth_amount or total
        notification = {
            'decision': decision,
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
            httpretty.register_uri(httpretty.GET, url, body=body)

    def get_soap_mock(self, amount=100, currency=CURRENCY, transaction_id=None, basket_id=None, decision='ACCEPT'):
        class CybersourceSoapMock(mock.MagicMock):
            def runTransaction(self, **kwargs):  # pylint: disable=unused-argument
                cc_reply_items = {
                    'reasonCode': 100,
                    'amount': unicode(amount),
                    'requestDateTime': '2015-01-01T:00:00:00Z',
                    'reconciliationID': 'efg456'
                }
                items = {
                    'requestID': transaction_id,
                    'decision': decision,
                    'merchantReferenceCode': unicode(basket_id),
                    'reasonCode': 100,
                    'requestToken': 'abc123',
                    'purchaseTotals': Factory.object('PurchaseTotals', {'currency': currency}),
                    'ccCreditReply': Factory.object('CCCreditReply', cc_reply_items)
                }

                return Factory.object('reply', items)

        return CybersourceSoapMock

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
            'consumer_id': basket.owner.username,
            'override_custom_receipt_page': get_receipt_page_url(
                order_number=basket.order_number,
                site_configuration=basket.site.siteconfiguration
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

        # Add the extra parameters
        expected.update(kwargs.get('extra_parameters', {}))

        # Generate a signature
        expected['signed_field_names'] = ','.join(sorted(expected.keys()))
        expected['signature'] = self.generate_signature(secret_key, expected)

        return expected


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

    def mock_api_response(self, path, body, post=True):
        assert httpretty.is_enabled()

        url = self._create_api_url(path)
        httpretty.register_uri(
            httpretty.POST if post else httpretty.GET,
            url,
            body=json.dumps(body),
            status=200
        )

    def mock_api_responses(self, path, response_array, post=True):
        assert httpretty.is_enabled()

        url = self._create_api_url(path)

        httpretty_response_array = []
        for response in response_array:
            httpretty_response_array.append(
                httpretty.Response(body=json.dumps(response['body']), status=response['status'])
            )

        httpretty.register_uri(
            httpretty.POST if post else httpretty.GET,
            url,
            responses=httpretty_response_array,
            status=200
        )

    def mock_oauth2_response(self):
        oauth2_response = {
            'scope': 'https://api.paypal.com/v1/payments/.*',
            'access_token': 'fake-access-token',
            'token_type': 'Bearer',
            'app_id': 'APP-123ABC',
            'expires_in': 28800
        }

        self.mock_api_response('/v1/oauth2/token', oauth2_response)

    def get_payment_creation_response_mock(self, basket,
                                           state=PAYMENT_CREATION_STATE, approval_url=APPROVAL_URL):

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
            self.mock_api_response(
                '/v1/payments/payment/{}'.format(self.PAYMENT_ID),
                payment_creation_response,
                post=False
            )
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
