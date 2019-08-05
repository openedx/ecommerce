""" Django management command to find frozen baskets missing payment response. """

import logging
import requests
import json
import datetime
import hashlib
import hmac
import base64
import pytz


from django.conf import settings
from django.db import transaction
from datetime import datetime, timedelta
from email.utils import formatdate
from datetime import datetime
from time import mktime
from urlparse import urlparse

from ecommerce_worker.fulfillment.v1.tasks import fulfill_order
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q, Subquery
from oscar.core.loading import get_class, get_model
from ecommerce.extensions.partner.strategy import DefaultStrategy

logger = logging.getLogger(__name__)
Basket = get_model('basket', 'Basket')
Order = get_model('order', 'Order')
BillingAddress = get_model('order', 'BillingAddress')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')
NoShippingRequired = get_class('shipping.methods', 'NoShippingRequired')
OrderTotalCalculator = get_class('checkout.calculators', 'OrderTotalCalculator')
Country = get_model('address', 'Country')
OrderCreator = get_class('order.utils', 'OrderCreator')


DEFAULT_START_DELTA_HOUR = 4
DEFAULT_END_DELTA_HOUR = 0



class CSConfiguration(object):
    def __init__(self, config):
        self.key = config['API_KEY_ID']
        self.secret_key = config['API_KEY_SECRET']
        self.host = config['HOST']
        self.merchant_id = config['MERCHANT_ID']


class CybersourceAPIClient(object):

    def __init__(self, cs_config):
        self.host = cs_config.host
        self.merchant_id = cs_config.merchant_id

        self.key = cs_config.key
        self.secret_key = cs_config.secret_key
        self.date_str = self.get_time_iso_format()

        self.digest = ''
        self.post_signature = ''
        self.get_signature = ''

    def generate_digest(self, message_body):

        hashobj = hashlib.sha256()
        hashobj.update(message_body.encode('utf-8'))
        hash_data = hashobj.digest()
        hashdigest = base64.b64encode(hash_data)

        self.digest = 'SHA-256=' + hashdigest.decode("utf-8")

    def generate_post_signature(self):
        signature_header = \
        "host: {host}\ndate: {date}\n(request-target): post /tss/v2/searches\ndigest: {digest}\nv-c-merchant-id: {merchant_id}"
        sig_value_string = signature_header.format(
            host=self.host,
            date=self.date_str,
            digest=self.digest,
            merchant_id=self.merchant_id)
        sig_value_utf = sig_value_string.encode('utf-8')

        # Signature string generated from above parameters is signed with secret key hashed with SHA-256
        # Secret key is base 64 decoded before signing
        secret = base64.b64decode(self.secret_key)
        hash_value = hmac.new(secret, sig_value_utf, hashlib.sha256)

        self.post_signature = base64.b64encode(hash_value.digest()).decode("utf-8")

    def request_message_body(self, order_number):
        json_body = {
            "offset": "0",
            "timezone": "America/Chicago",
            "query": "clientReferenceInformation.code:{order}".format(order=order_number),
            "name": "TSS search",
            "limit": "1",
            "save": "false",
            "sort": "id:desc, submitTimeUtc:desc"
        }

        message_body = json.dumps(json_body)
        message_body = message_body.replace(' ', '')

        return message_body

    def get_search_headers(self):

        headers = {
            'Accept-Encoding': '*',
            'User-Agent': 'Mozilla/5.0',
            'Accept': '*/*;charset=utf-8',
            'Host': self.host,
            'Date': self.date_str,
            'Content-Type': 'application/json;charset=utf-8',
            'v-c-merchant-id': self.merchant_id,
            'Digest': self.digest,
            'Signature': 'keyid="{keyid}", '
                         'algorithm="HmacSHA256", headers="host date (request-target) '
                         'digest v-c-merchant-id", '
                         'signature="{signature}"'.format(signature=self.post_signature, keyid=self.key)
        }
        return headers

    def generate_get_signature(self, path):
        signature_header = \
        "host: {host}\ndate: {date}\n(request-target): get {path}\nv-c-merchant-id: {merchant_id}"
        sig_value_string = signature_header.format(
            host=self.host,
            date=self.date_str,
            path=path,
            merchant_id=self.merchant_id)
        sig_value_utf = sig_value_string.encode('utf-8')

        # Signature string generated from above parameters is signed with secret key hashed with SHA-256
        # Secret key is base 64 decoded before signing
        secret = base64.b64decode(self.secret_key)
        hash_value = hmac.new(secret, sig_value_utf, hashlib.sha256)

        self.get_signature = base64.b64encode(hash_value.digest()).decode("utf-8")

    def get_transaction_headers(self):

        headers = {
            'Accept-Encoding': '*',
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/hal+json;charset=utf-8',
            'Host': self.host,
            'Date': self.date_str,
            'Content-Type': 'application/json;charset=utf-8',
            'v-c-merchant-id': self.merchant_id,
            'Signature': 'keyid="{keyid}", '
                         'algorithm="HmacSHA256", headers="host date (request-target) '
                         'v-c-merchant-id", '
                         'signature="{signature}"'.format(signature=self.get_signature, keyid=self.key)
        }
        return headers

    def get_time_iso_format(self):

        now = datetime.now()
        stamp = mktime(now.timetuple())
        date = str(formatdate(timeval=stamp, localtime=False, usegmt=True))

        return date


def check_cs_search_transaction(client, basket, message_body):
    """
    Hit Cybersource transaction search api to get meta details
    regarding a transaction.
    """

    try:
        response = requests.post('https://{host}/tss/v2/searches'.format(host=client.host),
                                 data=message_body,
                                 headers=client.get_search_headers())
    except Exception as e:
        logger.exception(u'Exception occurred while fetching detail for Order Number from Search api: [%s]: [%s]',
                         basket.order_number, e.message)
        raise

    if 201 == response.status_code:
        logger.info(u"Response from CyberSource Transaction Search api successful for Order Number " +
                    basket.order_number)
        search_transaction_response = json.loads(response.content)
        _process_search_transaction(search_transaction_response, basket, client)
    else:
        logger.info(u"Response from CyberSource Transaction Search api unsuccessful for Order Number " +
                    basket.order_number)
    return


def _process_search_transaction(transaction_response, basket, client):
    """Hit Cybersource transaction api to get details of a transaction."""

    try:
        transaction_summaries = transaction_response['_embedded']['transactionSummaries']

        if not transaction_summaries or len(transaction_summaries) == 0:
            logger.info(u"No summary info found from CyberSource "
                        u"Transaction Search api for Order Number: " + basket.order_number)
            return

        summary = transaction_summaries[0]
        application_summary = summary.get('applicationInformation', None)
        href = summary['_links']['transactionDetail']['href']

    except KeyError:
        logger.exception(u"Some information was not found in meta from CyberSource "
                    u"Transaction Search api for Order Number: " + basket.order_number)
        raise

    if not application_summary or not href:
        return

    success = False
    if 'applications' in application_summary:
        for app in application_summary['applications']:
            if 'ics_bill' == app['name'] and '100' == app['reasonCode']:
                success = True
                break
    if success:
        logger.info(u"Successfully found meta information from CyberSource "
                    u"Transaction Search api for Order Number: " + basket.order_number)

        href = href.replace(':-1', '')
        url = urlparse(href)
        client.generate_get_signature(url.path)

        try:
            # fetching transaction detail
            response = requests.get('https://{host}{path}'.format(host=client.host, path=url.path),
                                    headers=client.get_transaction_headers())
        except Exception as e:
            logger.exception(u'Exception occurred while fetching transaction detail for Order Number' 
                             u'from Transaction api: [%s]: %s', basket.order_number, e.message)
            raise

        transaction_detail = json.loads(response.content)
        _process_transaction_details(transaction_detail, basket)

    return


def _process_transaction_details(transaction, basket):
    """Processes details for a transaction."""

    application_summary = transaction.get('applicationInformation', None)

    if not application_summary:
        logger.info(u"Application summary information missing from transaction detail response "
                    u"for Order Number: " + basket.order_number)
        return

    if '100' == str(application_summary['reasonCode']):
        logger.info(u"Successfully found transaction information from CyberSource "
                    u"Transaction api for Order Number: " + basket.order_number)

        order_detail = {}
        order_information = transaction.get('orderInformation', None)

        if not order_information:
            logger.info(u"No order information found in transaction detail json "
                        u"for Order Number: " + basket.order_number)
            return

        bill_to = order_information.get('billTo', {})

        order_detail.update({
            'first_name': bill_to.get('firstName', 'first_name'),
            'last_name': bill_to.get('lastName', 'last_name'),
            'address': bill_to.get('address1', 'address1'),
            'zip': bill_to.get('postalCode', '12345'),
            'country': bill_to.get('country', 'US'),
        })

        amount_details = order_information.get('amountDetails', {})

        order_detail.update({
            'currency': amount_details.get('currency', 'USD'),
            'total_amount': amount_details.get('totalAmount', 0),
            'tax_amount': amount_details.get('taxAmount', 0),
        })

        _process_successful_order(order_detail, basket)
    else:
        logger.info(u"CS Transaction information shows unsucccessful transaction logged for Order Number " +
                    basket.order_number)


def _process_successful_order(order_detail, basket):
    logger.info(u"Processing Order Number: {order_number} for order creation."
                .format(order_number=basket.order_number))

    if not Order.objects.filter(number=basket.order_number).exists():
        logger.info(u"Order Number: {order_number} doesn't exist, creating it."
                    .format(order_number=basket.order_number))

        shipping_method = NoShippingRequired()
        shipping_charge = shipping_method.calculate(basket)
        user = basket.owner

        billing_info = BillingAddress(
            first_name=order_detail['first_name'],
            last_name=order_detail['last_name'],
            line1=order_detail['address'],

            # Oscar uses line4 for city
            line4='city',
            # Postal code is optional
            postcode=order_detail['zip'],
            # State is optional
            state='state',
            country=Country.objects.get(iso_3166_1_a2=order_detail['country'])
        )

        billing_info.save()

        site = basket.site
        order_data = {
            'basket': basket,
            'number': basket.order_number,
            'site': site,
            'partner': site.siteconfiguration.partner,
            'currency': order_detail['currency'],
            'total_incl_tax': order_detail['total_amount'],
            'total_excl_tax': order_detail['total_amount'],
            'shipping_incl_tax': shipping_charge.incl_tax,
            'shipping_excl_tax': shipping_charge.excl_tax,
            'shipping_method': shipping_method.name,
            'shipping_code': shipping_method.code,
            'user_id': user.id,
            'billing_address': billing_info,
            'status': 'Open'
        }

        basket.strategy = DefaultStrategy()
        with transaction.atomic():
            order = Order(**order_data)
            order.save()
            for line in basket.all_lines():
                OrderCreator().create_line_models(order, line)
                OrderCreator().update_stock_records(line)
            basket.submit()

            logger.info(u"Order Number: {order_number} created successfully."
                        .format(order_number=basket.order_number))

            logger.info(u'Requesting fulfillment of order [%s].', order.number)
            fulfill_order.delay(
                order.number,
                site_code=order.site.siteconfiguration.partner.short_code,
                email_opt_in=False
            )
    else:
        logger.info(u"Order Number: {order_number} already exist, skipping order creation."
                    .format(order_number=basket.order_number))


class InvalidTimeRange(Exception):
    """
    Exception raised explicitly when End Time is prior to Start Time
    """
    pass


class Command(BaseCommand):
    help = """
    Management command to find frozen baskets missing payment response

    This management command is responsible for checking the frozen baskets
    for which the payment form was submitted to Cybersource. It would
    fetch transaction details for all such frozen baskets and would try to create
    and fulfill such orders for all successful transactions.

    start-delta : Hours before now to start looking at frozen baskets that are missing
                  payment response
    end-delta : Hours before now to end looking at frozen baskets that are missing payment
                response. end-delta cannot be greater than start-delta
    Example:
        $ ... find_frozen_baskets_missing_payment_response --start-delta 240 --end-delta 60

    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--start-delta',
            dest='start_delta',
            action='store',
            type=int,
            default=DEFAULT_START_DELTA_HOUR,
            help='Hour before now to start looking at baskets.'
        )
        parser.add_argument(
            '--end-delta',
            dest='end_delta',
            action='store',
            type=int,
            default=DEFAULT_END_DELTA_HOUR,
            help='Hour before now to end looking at baskets.'
        )

    def handle(self, *args, **options):
        """
        Handler for the command

        It checks for date format and range validity and then
        calls find_frozen_baskets_missing_payment_response for
        the given date range
        """
        start_delta = options['start_delta']
        end_delta = options['end_delta']

        try:
            if end_delta > start_delta:
                raise InvalidTimeRange(u"Invalid time range")
        except InvalidTimeRange:
            logger.exception(u"Incorrect time range given.")
            return

        start = datetime.now(pytz.utc) - timedelta(hours=start_delta)
        end = datetime.now(pytz.utc) - timedelta(hours=end_delta)

        self.find_frozen_baskets_missing_payment_response(start, end)

    def find_frozen_baskets_missing_payment_response(self, start, end):
        """ Find baskets that are Frozen and missing payment response """

        config = self._get_configuration()

        if not config['API_KEY_ID'] or not config['API_KEY_SECRET']:
            raise CommandError(u"Missing API Key ID/KeySecret in configuration")
        if not config['HOST'] or not config['MERCHANT_ID']:
            raise CommandError(u"Missing API HOST/MERCHANT ID in configuration")

        cs_config = CSConfiguration(config)
        frozen_baskets = Basket.objects.filter(status='Frozen', date_submitted=None)

        frozen_baskets = frozen_baskets.filter(Q(date_created__gte=start, date_created__lt=end) |
                                               Q(date_merged__gte=start, date_merged__lt=end))
        frozen_baskets_missing_payment_response = \
            frozen_baskets.exclude(id__in=Subquery(PaymentProcessorResponse.objects.values_list('basket_id')))

        if not frozen_baskets_missing_payment_response:
            logger.info(u"No frozen baskets, missing payment response found")
        else:
            logger.info(u"Frozen baskets missing payment response found, checking with Cybersource..")
            frozen_baskets = set()
            orders_ids = []
            for basket in frozen_baskets_missing_payment_response:
                logger.info(u"Basket ID " + str(basket.id) + u" Order Number " + basket.order_number)
                frozen_baskets.add(basket)
                orders_ids.append(basket.order_number)

            ids = ','.join(orders_ids)
            logger.info(u"Checking Cybersource for orders: [{orders}]".format(orders=ids))

            self._check_transaction_from_cybersource(frozen_baskets, cs_config)

    def _check_transaction_from_cybersource(self, frozen_baskets, cs_config):

        client = CybersourceAPIClient(cs_config)

        for fb in frozen_baskets:
            try:
                message_body = client.request_message_body(fb.order_number)
                client.generate_digest(message_body)
                client.generate_post_signature()

                check_cs_search_transaction(client, fb, message_body)

            except Exception as e:
                continue

    def _get_configuration(self):

        CS_CONFIG = settings.CS_API_CONFIG

        return {
            'API_KEY_ID': CS_CONFIG.get('API_KEY_ID', None),
            'API_KEY_SECRET': CS_CONFIG.get('API_KEY_SECRET', None),
            'HOST': CS_CONFIG.get('host', None),
            'MERCHANT_ID': CS_CONFIG.get('merchant_id', None),
        }