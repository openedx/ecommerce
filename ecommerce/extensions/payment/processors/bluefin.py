""" Bluefin payment processing. """
from __future__ import absolute_import, unicode_literals

import logging
import requests
import json
from oscar.apps.payment.exceptions import TransactionDeclined
from oscar.core.loading import get_model

from ecommerce.extensions.payment.processors import (
    BaseClientSidePaymentProcessor,
    HandledProcessorResponse
)

logger = logging.getLogger(__name__)

BillingAddress = get_model('order', 'BillingAddress')
Country = get_model('address', 'Country')
PaymentEvent = get_model('order', 'PaymentEvent')
PaymentEventType = get_model('order', 'PaymentEventType')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')
Source = get_model('payment', 'Source')
SourceType = get_model('payment', 'SourceType')


class Bluefin(BaseClientSidePaymentProcessor):
    NAME = 'bluefin'
    template_name = 'payment/bluefin.html'

    @property
    def payment_processor(self):
        return Bluefin(self.request.site)

    def __init__(self, site):
        """
        Constructs a new instance of the Bluefin processor.

        Raises:
            KeyError: If no settings configured for this payment processor.
        """
        super(Bluefin, self).__init__(site)
        configuration = self.configuration
        self.account_id = configuration['merchant_account_id']
        self.api_key = configuration['api_access_key']
        self.post_url = configuration['post_api_url']

    def _get_basket_amount(self, basket):
        return str((basket.total_incl_tax * 100).to_integral_value())

    def handle_processor_response(self, request_data, basket=None):
        request_data['street_address1'] = request_data.pop(
            'address_line1', None)
        request_data['street_address2'] = request_data.pop(
            'address_line2', None)
        request_data['state'] = request_data.pop('country', None)
        request_data['zip'] = request_data.pop('postal_code', None)
        request_data['eToken'] = request_data.pop('bluefin_token', None)

        request_data.pop('csrfmiddlewaretoken', None)
        request_data.pop('basket', None)

        request_data['account_id'] = self.account_id
        request_data['api_accesskey'] = self.api_key
        request_data['response_format'] = 'JSON'
        request_data['transaction_type'] = 'SALE'
        request_data['tender_type'] = 'CARD'
        request_data['transaction_amount'] = str(
            basket.total_incl_tax.to_integral_value())

        response = requests.post(self.post_url, data=request_data)
        response = json.loads(response.content)

        if response['error']:
            msg = "Bluefin payment for basket [%d] declined with error msg:[%s]"
            body = response['error_message']
            logger.exception(msg, basket.id, body)
            self.record_processor_response(body, basket=basket)
            raise TransactionDeclined

        total = basket.total_incl_tax
        currency = basket.currency
        transaction_id = response['transaction_id']

        logger.info(
            'Successfull Bluefin Transaction [%s] for basket [%d].',
            transaction_id, basket.id
        )

        return HandledProcessorResponse(
            transaction_id=transaction_id,
            total=total,
            currency=currency,
            card_number=response['last4'],
            card_type=response['card_brand']
        )

    def issue_credit(
            self, order_number, basket, reference_number, amount, currency):
        raise NotImplementedError('The Bluefin payment processor does not \
            support issue_credit for Refund.')
