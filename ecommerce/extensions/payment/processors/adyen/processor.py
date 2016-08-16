""" Adyen payment processing. """
from __future__ import unicode_literals

from datetime import datetime
import json
import logging
from urlparse import urljoin

from django.db import transaction
from oscar.apps.payment.exceptions import GatewayError, PaymentError, TransactionDeclined
from oscar.core.loading import get_class, get_model
import requests

from ecommerce.core.constants import ISO_8601_FORMAT
from ecommerce.extensions.order.constants import PaymentEventTypeName
from ecommerce.extensions.payment.exceptions import NotificationParseError, UnknownBasketError
from ecommerce.extensions.payment.helpers import sign
from ecommerce.extensions.payment.processors.base import BasePaymentProcessor
from ecommerce.extensions.payment.utils import minor_units
from ecommerce.extensions.refund.status import REFUND


logger = logging.getLogger(__name__)

BillingAddress = get_model('order', 'BillingAddress')
Country = get_model('address', 'Country')
OrderNumberGenerator = get_class('order.utils', 'OrderNumberGenerator')
PaymentEvent = get_model('order', 'PaymentEvent')
PaymentEventType = get_model('order', 'PaymentEventType')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')
ProductClass = get_model('catalogue', 'ProductClass')
Source = get_model('payment', 'Source')
SourceType = get_model('payment', 'SourceType')


class Adyen(BasePaymentProcessor):
    """
    Adyen CSE Integration (June 2016)

    For reference, see https://docs.adyen.com/developers
    """

    ACCEPTED_NOTIFICATION_RESPONSE = '[accepted]'
    BASKET_TEMPLATE = 'adyen/basket.html'
    CONFIGURATION_MODEL = 'ecommerce.extensions.payment.processors.adyen.models.AdyenConfiguration'
    NAME = 'adyen'

    @property
    def generation_time(self):
        return datetime.utcnow().strftime(ISO_8601_FORMAT)

    def can_handle_notification(self, notification_data):
        try:
            self._parse_notification_items(notification_data)
        except NotificationParseError:
            return False

        return True

    def get_billing_address(self, payment_form_data):
        try:
            return BillingAddress(
                first_name=payment_form_data['first_name'],
                last_name=payment_form_data['last_name'],
                line1=payment_form_data['street_address'],
                line2=payment_form_data.get('apartment_number', ''),  # Address line 2 is optional
                line4=payment_form_data['city'],  # Oscar uses line4 for city
                postcode=payment_form_data['postal_code'],
                state=payment_form_data.get('state', ''),  # State is optional
                country=Country.objects.get(iso_3166_1_a2=payment_form_data['country'])
            )
        except KeyError:
            return None

    def get_transaction_parameters(self, basket, request=None):
        """
        Generate a dictionary of parameters Adyen requires to complete a transaction.

        Arguments:
            basket (Basket): The basket of products being purchase.; not used by this method.

        Keyword Arguments:
            request (Request): A Request object which could be used to construct an absolute URL; not
                used by this method.

        Returns:
            dict: Adyen-specific parameters required to complete a transaction.
        """
        parameters = {
            'payment_page_url': '',
        }

        return parameters

    def handle_payment_authorization_response(self, response, basket):
        transaction_id = response['pspReference']
        result_code = response['resultCode'].lower()

        if result_code != 'authorised':
            raise TransactionDeclined

        return self._process_authorization(transaction_id, basket)

    def issue_credit(self, source, amount, currency):
        order = source.order

        response = requests.post(
            urljoin(self.configuration.payment_api_url, 'cancelOrRefund'),
            auth=(self.configuration.web_service_username, self.configuration.web_service_password),
            headers={
                'Content-Type': 'application/json'
            },
            json={
                'merchantAccount': self.configuration.merchant_account_code,
                'originalReference': source.reference,
                'reference': order.number
            }
        )

        adyen_response = response.json()

        try:
            if response.status_code == requests.codes.ok:
                self.record_processor_response(
                    response.json(),
                    transaction_id=adyen_response['pspReference'],
                    basket=order.basket
                )
                if adyen_response['response'] != '[cancelOrRefund-received]':
                    raise GatewayError
            else:
                raise GatewayError
        except GatewayError:
            msg = 'An error occurred while attempting to issue a credit (via Adyen) for order [{}].'.format(
                order.number
            )
            logger.exception(msg)
            raise GatewayError(msg)

        return False

    def process_notification(self, notification_data):
        """
        Handle notification/response from Adyen.
        """
        self.record_processor_response()
        try:
            notification_items = self._parse_notification_items(notification_data)
        except NotificationParseError:
            payment_processor_response = self.record_processor_response(notification_data)
            logger.error(
                'Received invalid Adyen notification. '
                'The payment processor response was recorded in record [%d].',
                payment_processor_response.id
            )

        for notification_item in notification_items:
            transaction_id = None
            try:
                notification = notification_item['NotificationRequestItem']
                transaction_id = notification['pspReference']
                order_number = notification['merchantReference']
            except KeyError:
                payment_processor_response = self.record_processor_response(notification_item, transaction_id)
                logger.error(
                    'Received invalid Adyen notification for transaction [%s].'
                    'The payment processor response was recorded in record [%d].',
                    transaction_id,
                    payment_processor_response.id
                )
                continue

            if not self._is_signature_valid(notification):
                payment_processor_response = self.record_processor_response(notification, transaction_id)
                logger.error(
                    'Adyen notification HMAC signature verification failed for transaction [%s].'
                    'The payment processor response was recorded in record [%d].',
                    transaction_id,
                    payment_processor_response.id
                )
                continue

            basket_id = OrderNumberGenerator().basket_id(order_number)
            try:
                basket = self._get_basket(basket_id)
            except UnknownBasketError:
                payment_processor_response = self.record_processor_response(notification, transaction_id)
                logger.error(
                    'Received Adyen notification for transaction [%s], associated with unknown basket [%s].'
                    'The payment processor response was recorded in record [%d].',
                    transaction_id,
                    basket_id,
                    payment_processor_response.id
                )
                continue

            payment_processor_response = self.record_processor_response(notification, transaction_id, basket)
            logger.info(
                'Received Adyen notification for transaction [%s], associated with basket [%s].'
                'The payment processor response was recorded in record [%d].',
                transaction_id,
                basket_id,
                payment_processor_response.id
            )

            # Explicitly delimit operations which will be rolled back if an exception occurs.
            with transaction.atomic():
                try:
                    event_code = notification['eventCode']
                    return getattr(
                        self,
                        '_handle_{event}'.format(event=event_code.lower())
                    )(transaction_id, notification)
                except KeyError:
                    logger.error(
                        'Received Adyen notification with missing eventCode for transaction [%s], '
                        'associated with basket [%s].'
                        'The payment processor response was recorded in record [%d].',
                        transaction_id,
                        basket.order_number,
                        payment_processor_response
                    )
                    continue
                except AttributeError:
                    logger.error(
                        'Received Adyen notification with unsupported Adyen eventCode [%s] '
                        'for transaction [%s], associated with basket [%s].'
                        'The payment processor response was recorded in record [%d].',
                        event_code,
                        transaction_id,
                        basket.order_number,
                        payment_processor_response
                    )
                    continue

    def send_payment_authorization_request(self, basket, authorization_data):
        """
        Send authorise API request to Adyen to authorize payment.
        """
        request_url = urljoin(self.configuration.payment_api_url, 'authorise')
        request_payload = {
            'additionalData': {
                'card.encrypted.json': authorization_data['adyen-encrypted-data']
            },
            'amount': {
                'value': minor_units(basket.total_incl_tax, basket.currency),
                'currency': basket.currency
            },
            'reference': basket.order_number,
            'merchantAccount': self.configuration.merchant_account_code
        }

        # Add additional shopper data collected on payment form
        request_payload.update(self._get_shopper_data(**authorization_data))

        response = requests.post(
            request_url,
            auth=(self.configuration.web_service_username, self.configuration.web_service_password),
            headers={
                'Content-Type': 'application/json'
            },
            json=request_payload
        )

        if response.status_code != requests.codes.OK:
            logger.error(
                'Adyen payment authorization failed with status [%d] for basket [%s].',
                response.status_code,
                basket.order_number,
            )
            raise PaymentError

        adyen_response = response.json()
        transaction_id = adyen_response.get('pspReference')
        result_code = adyen_response.get('resultCode')
        payment_processor_response = self.record_processor_response(adyen_response, transaction_id, basket)

        logger.info(
            'Received Adyen payment authorization response with result code [%s] for transaction [%s], '
            'associated with basket [%s]. '
            'The payment processor response was recorded in record [%d].',
            result_code,
            transaction_id,
            basket.order_number,
            payment_processor_response.id
        )

        return payment_processor_response

    def _generate_signature(self, notification):
        amount = notification.get('amount', {})
        signed_values = [
            notification.get('pspReference', ''),
            notification.get('originalReference', ''),
            notification.get('merchantAccountCode', ''),
            notification.get('merchantReference', ''),
            amount.get('value', ''),
            amount.get('currencyCode'),
            notification.get('eventCode', ''),
            str(notification.get('success', '')).lower()
        ]
        message = ':'.join(signed_values)

        return sign(message, self.configuration.notifications_hmac_key)

    def _get_shopper_data(self, **kwargs):
        return {
            'shopper_name': {
                'firstName': kwargs.get('first_name', ''),
                'lastName': kwargs.get('last_name', '')
            },
            'shopperEmail': kwargs.get('email', ''),
            'billingAddress': {
                'street': kwargs.get('street_address', ''),
                'houseNumberOrName': kwargs.get('apartment_number', ''),
                'city': kwargs.get('city', ''),
                'stateOrProvince': kwargs.get('state', ''),
                'postalCode': kwargs.get('postal_code', ''),
                'country': kwargs.get('country', '')
            },
            'shopperIP': kwargs.get('ip', '')
        }

    def _handle_authorisation(self, psp_reference, response, basket):
        pass

    def _handle_cancel_or_refund(self, transaction_id, response, basket):
        order = basket.order_set.first()
        # TODO Update this if we ever support multiple payment sources for a single order.
        source = order.sources.first()
        refund = order.refunds.get(status__in=[REFUND.PENDING_WITH_REVOCATION, REFUND.PENDING_WITHOUT_REVOCATION])
        amount = refund.total_credit_excl_tax
        if response.get('success'):
            source.refund(amount, reference=transaction_id)
            revoke_fulfillment = refund.status == REFUND.PENDING_WITH_REVOCATION
            refund.set_status(REFUND.PAYMENT_REFUNDED)
            refund.complete(revoke_fulfillment)
            event_type, __ = PaymentEventType.objects.get_or_create(name=PaymentEventTypeName.REFUNDED)
            PaymentEvent.objects.create(
                event_type=event_type,
                order=order,
                amount=amount,
                reference=transaction_id,
                processor_name=self.NAME
            )
        else:
            logger.error('Adyen refund request failed for order [%s]', order.number)

    def _is_signature_valid(self, notification):
        try:
            return self._generate_signature(notification) == notification['additionalData']['hmacSignature']
        except KeyError:
            logger.exception('Invalid Adyen HMAC signature')
            return False

    def _parse_notification_items(self, notification_data):
        try:
            return json.loads(notification_data)['notificationItems']
        except (ValueError, KeyError):
            raise NotificationParseError

    def _process_authorization(self, transaction_id, basket):
        # Create Source to track all transactions related to this processor and order
        source_type, __ = SourceType.objects.get_or_create(name=self.NAME)
        currency = basket.currency
        total = basket.total_incl_tax

        source = Source(
            source_type=source_type,
            currency=currency,
            amount_allocated=total,
            amount_debited=total,
            reference=transaction_id
        )

        # Create PaymentEvent to track
        event_type, __ = PaymentEventType.objects.get_or_create(name=PaymentEventTypeName.PAID)
        event = PaymentEvent(event_type=event_type, amount=total, reference=transaction_id, processor_name=self.NAME)

        return source, event
