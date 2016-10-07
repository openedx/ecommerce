import json
import os
from urlparse import urljoin

from django.conf import settings
import httpretty
import mock
from oscar.core.loading import get_model
from oscar.test import newfactories
from suds.sudsobject import Factory

from ecommerce.extensions.payment.constants import CARD_TYPES
from ecommerce.extensions.payment.helpers import sign

CURRENCY = u'USD'
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
        keys = data[u'signed_field_names'].split(u',')

        message = u','.join([u'{key}={value}'.format(key=key, value=data[key]) for key in keys])
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

    def generate_notification(self, secret_key, basket, decision=u'ACCEPT', billing_address=None, auth_amount=None,
                              **kwargs):
        """ Generates a dict containing the API reply fields expected to be received from CyberSource. """

        req_reference_number = kwargs.get('req_reference_number', basket.order_number)
        total = unicode(basket.total_incl_tax)
        auth_amount = auth_amount or total
        notification = {
            u'req_transaction_type': u'sale',
            u'decision': decision,
            u'req_reference_number': req_reference_number,
            u'transaction_id': u'123456',
            u'auth_amount': auth_amount,
            u'req_amount': total,
            u'req_tax_amount': u'0.00',
            u'req_currency': basket.currency,
            u'req_card_number': u'xxxxxxxxxxxx1111',
            u'req_card_type': CARD_TYPES[self.DEFAULT_CARD_TYPE]['cybersource_code']
        }

        if billing_address:
            notification.update({
                u'req_bill_to_forename': billing_address.first_name,
                u'req_bill_to_surname': billing_address.last_name,
                u'req_bill_to_address_line1': billing_address.line1,
                u'req_bill_to_address_city': billing_address.line4,
                u'req_bill_to_address_postal_code': billing_address.postcode,
                u'req_bill_to_address_country': billing_address.country.iso_3166_1_a2
            })

            # handle optional address fields
            if billing_address.line2:
                notification[u'req_bill_to_address_line2'] = billing_address.line2
            if billing_address.state:
                notification[u'req_bill_to_address_state'] = billing_address.state

        notification[u'signed_field_names'] = u','.join(notification.keys())
        notification[u'signature'] = self.generate_signature(secret_key, notification)
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


class PaypalMixin(object):
    """Mixin with helper methods for mocking PayPal API responses."""
    APPROVAL_URL = u'https://api.sandbox.paypal.com/fake-approval-url'
    EMAIL = u'test-buyer@paypal.com'
    PAYER_ID = u'PAYERID'
    PAYMENT_ID = u'PAY-123ABC'
    PAYMENT_CREATION_STATE = u'created'
    PAYMENT_EXECUTION_STATE = u'approved'
    PAYER_INFO = {
        u'email': EMAIL,
        u'first_name': u'test',
        u'last_name': u'buyer',
        u'payer_id': u'123ABC',
        u'shipping_address': {
            u'city': u'San Jose',
            u'country_code': u'US',
            u'line1': u'1 Main St',
            u'postal_code': u'95131',
            u'recipient_name': u'test buyer',
            u'state': u'CA'
        }
    }
    RETURN_DATA = {
        u'paymentId': PAYMENT_ID,
        u'PayerID': PAYER_ID
    }
    SALE_ID = u'789XYZ'

    def mock_api_response(self, path, body, post=True):
        assert httpretty.is_enabled()

        url = self._create_api_url(path)
        httpretty.register_uri(
            httpretty.POST if post else httpretty.GET,
            url,
            body=json.dumps(body),
            status=200
        )

    def mock_oauth2_response(self):
        oauth2_response = {
            u'scope': u'https://api.paypal.com/v1/payments/.*',
            u'access_token': u'fake-access-token',
            u'token_type': u'Bearer',
            u'app_id': u'APP-123ABC',
            u'expires_in': 28800
        }

        self.mock_api_response('/v1/oauth2/token', oauth2_response)

    def mock_payment_creation_response(self, basket, state=PAYMENT_CREATION_STATE, approval_url=APPROVAL_URL,
                                       find=False):
        total = unicode(basket.total_incl_tax)
        payment_creation_response = {
            u'create_time': u'2015-05-04T18:18:27Z',
            u'id': self.PAYMENT_ID,
            u'intent': u'sale',
            u'links': [
                {
                    u'href': u'https://api.sandbox.paypal.com/v1/payments/payment/{}'.format(self.PAYMENT_ID),
                    u'method': u'GET',
                    u'rel': u'self'
                },
                {
                    u'href': u'https://api.sandbox.paypal.com/v1/payments/payment/{}/execute'.format(self.PAYMENT_ID),
                    u'method': u'POST',
                    u'rel': u'execute'
                }
            ],
            u'payer': {
                u'payer_info': {u'shipping_address': {}},
                u'payment_method': u'paypal'
            },
            u'redirect_urls': {
                u'cancel_url': u'http://fake-cancel-page',
                u'return_url': u'http://fake-return-url'
            },
            u'state': state,
            u'transactions': [{
                u'amount': {
                    u'currency': CURRENCY,
                    u'details': {u'subtotal': total},
                    u'total': total
                },
                u'item_list': {
                    u'items': [
                        {
                            u'quantity': line.quantity,
                            u'name': line.product.title,
                            u'price': unicode(line.line_price_incl_tax_incl_discounts / line.quantity),
                            u'currency': line.stockrecord.price_currency,
                        }
                        for line in basket.all_lines()
                    ],
                },
                u'invoice_number': basket.order_number,
                u'related_resources': []
            }],
            u'update_time': u'2015-05-04T18:18:27Z'
        }

        if approval_url:
            payment_creation_response[u'links'].append({
                u'href': approval_url,
                u'method': u'REDIRECT',
                u'rel': u'approval_url'
            })

        if find:
            self.mock_api_response(
                '/v1/payments/payment/{}'.format(self.PAYMENT_ID),
                payment_creation_response,
                post=False
            )
        else:
            self.mock_api_response('/v1/payments/payment', payment_creation_response)

        return payment_creation_response

    def mock_payment_execution_response(self, basket, state=PAYMENT_EXECUTION_STATE, payer_info=None):
        if payer_info is None:
            payer_info = self.PAYER_INFO
        total = unicode(basket.total_incl_tax)
        payment_execution_response = {
            u'create_time': u'2015-05-04T15:55:27Z',
            u'id': self.PAYMENT_ID,
            u'intent': u'sale',
            u'links': [{
                u'href': u'https://api.sandbox.paypal.com/v1/payments/payment/{}'.format(self.PAYMENT_ID),
                u'method': u'GET',
                u'rel': u'self'
            }],
            u'payer': {
                u'payer_info': payer_info,
                u'payment_method': u'paypal'
            },
            u'redirect_urls': {
                u'cancel_url': u'http://fake-cancel-page',
                u'return_url': u'http://fake-return-url'
            },
            u'state': state,
            u'transactions': [{
                u'amount': {
                    u'currency': CURRENCY,
                    u'details': {u'subtotal': total},
                    u'total': total
                },
                u'item_list': {
                    u'items': [
                        {
                            u'quantity': line.quantity,
                            u'name': line.product.title,
                            u'price': unicode(line.line_price_incl_tax_incl_discounts / line.quantity),
                            u'currency': line.stockrecord.price_currency,
                        }
                        for line in basket.all_lines()
                    ],
                },
                u'invoice_number': basket.order_number,
                u'related_resources': [{
                    u'sale': {
                        u'amount': {
                            u'currency': CURRENCY,
                            u'total': total
                        },
                        u'create_time': u'2015-05-04T15:55:27Z',
                        u'id': self.SALE_ID,
                        u'links': [
                            {
                                u'href': u'https://api.sandbox.paypal.com/v1/payments/sale/{}'.format(self.SALE_ID),
                                u'method': u'GET',
                                u'rel': u'self'
                            },
                            {
                                u'href': u'https://api.sandbox.paypal.com/v1/payments/sale/{}/refund'.format(
                                    self.SALE_ID
                                ),
                                u'method': u'POST',
                                u'rel': u'refund'
                            },
                            {
                                u'href': u'https://api.sandbox.paypal.com/v1/payments/payment/{}'.format(
                                    self.PAYMENT_ID
                                ),
                                u'method': u'GET',
                                u'rel': u'parent_payment'
                            }
                        ],
                        u'parent_payment': self.PAYMENT_ID,
                        u'payment_mode': u'INSTANT_TRANSFER',
                        u'protection_eligibility': u'ELIGIBLE',
                        u'protection_eligibility_type': u'ITEM_NOT_RECEIVED_ELIGIBLE,UNAUTHORIZED_PAYMENT_ELIGIBLE',
                        u'state': u'completed',
                        u'transaction_fee': {
                            u'currency': CURRENCY,
                            u'value': u'0.50'
                        },
                        u'update_time': u'2015-05-04T15:58:47Z'
                    }
                }]
            }],
            u'update_time': u'2015-05-04T15:58:47Z'
        }

        self.mock_api_response(
            '/v1/payments/payment/{}/execute'.format(self.PAYMENT_ID),
            payment_execution_response
        )

        return payment_execution_response

    def _create_api_url(self, path):
        mode = settings.PAYMENT_PROCESSOR_CONFIG['edx']['paypal']['mode']
        root = u'https://api.sandbox.paypal.com' if mode == 'sandbox' else u'https://api.paypal.com'

        return urljoin(root, path)
