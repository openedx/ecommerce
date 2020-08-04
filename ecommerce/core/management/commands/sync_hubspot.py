"""
Django management command to Sync Product, Orders and Lines to Hubspot server.
"""


import json
import logging
import time
import traceback
from datetime import datetime, timedelta
from decimal import Decimal as D

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from edx_rest_api_client.client import EdxRestApiClient
from oscar.core.loading import get_class, get_model
from slumber.exceptions import HttpClientError, HttpServerError

from ecommerce.extensions.fulfillment.status import ORDER

Basket = get_model('basket', 'Basket')
CartLine = get_model('basket', 'Line')
Order = get_model('order', 'Order')
OrderLine = get_model('order', 'Line')
OrderNumberGenerator = get_class('order.utils', 'OrderNumberGenerator')
Product = get_model('catalogue', 'Product')
SiteConfiguration = get_model('core', 'SiteConfiguration')
User = get_user_model()
logger = logging.getLogger(__name__)


DEFAULT_INITIAL_DAYS = 1
HUBSPOT_API_BASE_URL = 'https://api.hubapi.com'
HUBSPOT_ECOMMERCE_SETTINGS = {
    'enabled': True,
    'productSyncSettings': {
        'properties': [
            {
                'propertyName': 'date_created',
                'dataType': 'DATETIME',
                'targetHubspotProperty': 'createdate'
            },
            {
                'propertyName': 'title',
                'dataType': 'STRING',
                'targetHubspotProperty': 'name'
            },
            {
                'propertyName': 'description',
                'dataType': 'STRING',
                'targetHubspotProperty': 'description'
            }
        ]
    },
    'dealSyncSettings': {
        'properties': [
            {
                'propertyName': 'total_incl_tax',
                'dataType': 'NUMBER',
                'targetHubspotProperty': 'amount'
            },
            {
                'propertyName': 'checkout_status',
                'dataType': 'STRING',
                'targetHubspotProperty': 'dealstage'
            },
            {
                'propertyName': 'date_created',
                'dataType': 'DATETIME',
                'targetHubspotProperty': 'createdate'
            },
            {
                'propertyName': 'date_placed',
                'dataType': 'DATETIME',
                'targetHubspotProperty': 'closedate'
            },
            {
                'propertyName': 'description',
                'dataType': 'STRING',
                'targetHubspotProperty': 'description'
            },
            {
                'propertyName': 'number',
                'dataType': 'STRING',
                'targetHubspotProperty': 'ip__ecomm_bridge__order_number'
            },
            {
                'propertyName': 'deal_name',
                'dataType': 'STRING',
                'targetHubspotProperty': 'dealname'
            },
            {
                'propertyName': 'user_id',
                'dataType': 'STRING',
                'targetHubspotProperty': 'hs_assoc__contact_ids'
            }
        ]
    },
    'lineItemSyncSettings': {
        'properties': [
            {
                'propertyName': 'price_incl_tax',
                'dataType': 'NUMBER',
                'targetHubspotProperty': 'amount'
            },
            {
                'propertyName': 'price_excl_tax',
                'dataType': 'NUMBER',
                'targetHubspotProperty': 'price'
            },
            {
                'propertyName': 'tax',
                'dataType': 'NUMBER',
                'targetHubspotProperty': 'tax'
            },
            {
                'propertyName': 'price_currency',
                'dataType': 'STRING',
                'targetHubspotProperty': 'hs_line_item_currency_code'
            },
            {
                'propertyName': 'quantity',
                'dataType': 'NUMBER',
                'targetHubspotProperty': 'quantity'
            },
            {
                'propertyName': 'order_id',
                'dataType': 'STRING',
                'targetHubspotProperty': 'hs_assoc__deal_id'
            },
            {
                'propertyName': 'product_id',
                'dataType': 'STRING',
                'targetHubspotProperty': 'hs_assoc__product_id'
            },
            {
                'propertyName': 'date_created',
                'dataType': 'DATETIME',
                'targetHubspotProperty': 'createdate'
            }
        ]
    },
    'contactSyncSettings': {
        'properties': [
            {
                'propertyName': 'email',
                'dataType': 'STRING',
                'targetHubspotProperty': 'email'
            }
        ]
    }
}
CHECKOUT_PENDING = "checkout_pending"
CHECKOUT_ABANDONED = "checkout_abandoned"
CHECKOUT_COMPLETED = "checkout_completed"
PROCESSED = "processed"
BASKET_TO_HUBSPOT_STATUS = {
    Basket.OPEN: CHECKOUT_PENDING,
    Basket.MERGED: CHECKOUT_PENDING,
    Basket.SAVED: CHECKOUT_ABANDONED,
    Basket.FROZEN: CHECKOUT_PENDING,
    Basket.SUBMITTED: CHECKOUT_COMPLETED,
}

ORDER_TO_HUBSPOT_STATUS = {
    ORDER.OPEN: CHECKOUT_COMPLETED,
    ORDER.FULFILLMENT_ERROR: CHECKOUT_COMPLETED,
    ORDER.COMPLETE: PROCESSED
}
CONTACT = "CONTACT"
PRODUCT = "PRODUCT"
LINE_ITEM = "LINE_ITEM"
DEAL = "DEAL"
BATCH_SIZE = 200


class Command(BaseCommand):
    help = 'Sync Product, Orders and Lines to Hubspot server.'
    initial_sync_days = None

    def _get_hubspot_enable_sites(self):
        """
        Returns all SiteConfigurations which have hubspot enabled.
        """
        return SiteConfiguration.objects.exclude(hubspot_secret_key='')

    def _hubspot_endpoint(self, hubspot_object, api_url, method, body=None, **kwargs):
        """
        This function is responsible for all the calls of hubspot.
        """
        client = EdxRestApiClient('/'.join([HUBSPOT_API_BASE_URL, api_url]))
        if method == "GET":
            return getattr(client, hubspot_object).get(**kwargs)
        if method == "POST":
            return getattr(client, hubspot_object).post(**kwargs)
        if method == "PUT":
            return getattr(client, hubspot_object).put(body, **kwargs)
        raise ValueError("Unexpected method {}".format(method))

    def _install_hubspot_ecommerce_bridge(self, site_configuration):
        """
        Installs hubspot bridge for given site_configuration.
        """
        status = False
        try:
            self._hubspot_endpoint(
                'installs',
                'extensions/ecomm/v1/',
                'POST',
                hapikey=site_configuration.hubspot_secret_key
            )
            self.stdout.write(
                'Successfully installed hubspot ecommerce bridge for site {site}'.format(
                    site=site_configuration.site.domain
                )
            )
            status = True
        except (HttpClientError, HttpServerError) as ex:
            self.stderr.write(
                'An error occurred while installing hubspot ecommerce bridge for site {site}, {message}'.format(
                    site=site_configuration.site.domain, message=ex
                )
            )
        return status

    def _define_hubspot_ecommerce_settings(self, site_configuration):
        """
        Defines hubspot ecommerce settings for given site_configuration.
        """
        status = False
        try:
            self._hubspot_endpoint(
                'settings',
                'extensions/ecomm/v1/',
                'PUT',
                body=HUBSPOT_ECOMMERCE_SETTINGS,
                hapikey=site_configuration.hubspot_secret_key
            )
            self.stdout.write(
                'Successfully defined the hubspot ecommerce settings for site {site}'.format(
                    site=site_configuration.site.domain
                )
            )
            status = True
        except (HttpClientError, HttpServerError) as ex:
            self.stderr.write(
                'An error occurred while defining hubspot ecommerce settings for site {site}, {message}'.format(
                    site=site_configuration.site.domain, message=ex
                )
            )
        return status

    def _get_timestamp(self, date=None):
        """
        If date is given then returns its timestamp
        otherwise returns the current timestamp.
        """
        if date:
            timestamp = (date - datetime(1970, 1, 1, tzinfo=date.tzinfo)).total_seconds()
        else:
            timestamp = time.time()
        return int(timestamp * 1000)

    def _get_carts_extra_properties(self, cart):
        total_price = D(0.0)
        description = ''
        lines = cart.all_lines()
        for line in lines:
            total_price += self._get_cart_line_prices(line, 'price_incl_tax')
            description += self._get_cart_line_information(line)
        return float(total_price), description

    def _get_cart_line_prices(self, line, attr):
        return getattr(line, attr, D(0.0)) * line.quantity

    def _get_cart_line_information(self, line):
        return json.dumps({
            'Product': "{title} {course_id}".format(
                title=line.product.title,
                course_id=line.product.course.id if line.product.course else ''
            ),
            'Currency': line.price_currency,
            'Price including tax': float(self._get_cart_line_prices(line, 'price_incl_tax')),
            'Price': float(self._get_cart_line_prices(line, 'price_excl_tax')),
            'Quantity': line.quantity
        })

    def _get_hubspot_contact_structure(self, users):
        """
        Returns list of dicts, each dict represents hubspot CONTACT.
        """
        hubspot_contacts = []
        for user in users:
            hubspot_contacts.append({
                'integratorObjectId': str(user.id),
                'action': 'UPSERT',
                'changeOccurredTimestamp': self._get_timestamp(),
                'propertyNameToValues': {
                    'email': user.email
                }
            })
        return hubspot_contacts

    def _get_hubspot_deal_structure(self, carts, partner):
        """
        Returns list of dicts, each dict represents hubspot DEAL.
        """
        hubspot_deals = []
        for cart in carts:
            deal = {
                'integratorObjectId': str(cart.id),
                'action': 'UPSERT',
                'changeOccurredTimestamp': self._get_timestamp(),
                'propertyNameToValues': {}
            }
            total_price, description = self._get_carts_extra_properties(cart)
            if cart.status == Basket.SUBMITTED:
                order = Order.objects.filter(basket=cart).first()
                deal['propertyNameToValues'] = {
                    'deal_name': order.number,
                    'total_incl_tax': float(order.total_incl_tax),
                    'checkout_status': ORDER_TO_HUBSPOT_STATUS.get(order.status),
                    'date_placed': self._get_timestamp(date=order.date_placed),
                    'number': order.number,
                    'user_id': str(order.user.id) if order.user else ''
                }
            else:
                deal['propertyNameToValues'] = {
                    'deal_name': OrderNumberGenerator().order_number_from_basket_id(partner, cart.id),
                    'total_incl_tax': total_price,
                    'checkout_status': BASKET_TO_HUBSPOT_STATUS.get(cart.status),
                    'user_id': str(cart.owner.id) if cart.owner else ''
                }
            deal['propertyNameToValues']['description'] = description
            hubspot_deals.append(deal)
        return hubspot_deals

    def _get_hubspot_line_item_structure(self, lines):
        """
        Returns list of dicts, each dict represents hubspot LINE_ITEM.
        """
        hubspot_line_items = []
        for line in lines:
            line_price_incl_tax = self._get_cart_line_prices(line, 'price_incl_tax')
            line_price_excl_tax = self._get_cart_line_prices(line, 'price_excl_tax')
            hubspot_line_items.append({
                'integratorObjectId': str(line.id),
                'action': 'UPSERT',
                'changeOccurredTimestamp': self._get_timestamp(),
                'propertyNameToValues': {
                    'order_id': str(line.basket.id),
                    'price_currency': str(line.price_currency),
                    'tax': float(line_price_incl_tax - line_price_excl_tax),
                    'product_id': str(line.product.id),
                    'price_incl_tax': float(line_price_incl_tax),
                    'price_excl_tax': float(line_price_excl_tax),
                    'quantity': line.quantity
                }
            })
        return hubspot_line_items

    def _get_hubspot_product_structure(self, products):
        """
        Returns list of dicts, each dict represents hubspot PRODUCT.
        """
        hubspot_products = []
        for product in products:
            if product.description:
                description = product.description
            else:
                description = product.course.id if product.course else ''
            hubspot_products.append({
                'integratorObjectId': str(product.id),
                'action': 'UPSERT',
                'changeOccurredTimestamp': self._get_timestamp(),
                'propertyNameToValues': {
                    'title': str(product.title),
                    'description': description
                }
            })
        return hubspot_products

    def _upsert_hubspot_objects(self, object_type, objects, site_configuration):
        """
        Calls the sync message endpoint on given objects (PRODUCT, DEAL
        and LINE_ITEM) and each request can has 200 (BATCH_SIZE) objects.
        """
        try:
            total = len(objects)
            for start in range(0, total, BATCH_SIZE):
                batch = objects[start:start + BATCH_SIZE]
                self.stdout.write(
                    'Syncing {object_type}s batch from {start} to {end} of total: {total} for site {site}'.format(
                        object_type=object_type,
                        start=start,
                        end=start + BATCH_SIZE,
                        total=total,
                        site=site_configuration.site.domain
                    )
                )
                self._hubspot_endpoint(
                    object_type,
                    'extensions/ecomm/v1/sync-messages/',
                    'PUT',
                    body=batch,
                    hapikey=site_configuration.hubspot_secret_key
                )
                self.stdout.write(
                    'Successfully synced {object_type}s batch from {start} to {end} of total: '
                    '{total} for site {site}'.format(
                        object_type=object_type,
                        start=start,
                        end=start + BATCH_SIZE,
                        total=total,
                        site=site_configuration.site.domain
                    )
                )
        except (HttpClientError, HttpServerError) as ex:
            self.stderr.write(
                'An error occurred while upserting {object_type} for site {site}: {message}'.format(
                    object_type=object_type, site=site_configuration.site.domain, message=ex
                )
            )

    def _call_sync_errors_messages_endpoint(self, site_configuration):
        """
        Calls the sync error endpoint and print the response.
        """
        try:
            response = self._hubspot_endpoint(
                'sync-errors',
                'extensions/ecomm/v1/',
                'GET',
                hapikey=site_configuration.hubspot_secret_key
            )
            for error in response.get('results'):
                self.stdout.write(
                    'sync-error endpoint: for {object_type} with id {id} for site {site}: {message}'.format(
                        object_type=error.get('objectType'),
                        id=error.get('integratorObjectId'),
                        site=site_configuration.site.domain,
                        message=error.get('details')
                    )
                )
        except (HttpClientError, HttpServerError) as ex:
            self.stderr.write(
                'An error occurred while getting the error syncing message for site {site}: {message} '.format(
                    site=site_configuration.site.domain, message=ex
                )
            )

    def _get_unsynced_carts(self, site_configuration):
        carts = Basket.objects.filter(site=site_configuration.site, lines__isnull=False)
        start_date = datetime.now().date() - timedelta(self.initial_sync_days)
        unsynced_carts = carts.filter(
            Q(date_created__date=start_date) | Q(date_submitted__date=start_date)
        )
        self.stdout.write(
            'Pulled unsynced carts for site {site} from {start_date} and total count is total: {count}'.format(
                site=site_configuration.site.domain, start_date=start_date, count=unsynced_carts.count()
            )
        )
        return unsynced_carts

    def _sync_data(self, site_configuration):
        """
        Create lists of Order, OrderLine and Product objects and
        call upsert(PUT) sync-messages endpoint for each objects.
        """
        unsynced_carts = self._get_unsynced_carts(site_configuration)
        if unsynced_carts:
            # we need to exclude the CartLines without product
            # because product is required in hubspot for LINE_ITEM.
            unsynced_cart_lines = CartLine.objects.filter(basket__in=unsynced_carts).exclude(product=None)
            unsynced_products = Product.objects.filter(basket_lines__in=unsynced_cart_lines)
            unsynced_users = User.objects.filter(baskets__in=unsynced_carts)
            self._upsert_hubspot_objects(
                CONTACT,
                self._get_hubspot_contact_structure(unsynced_users),
                site_configuration
            )
            self._upsert_hubspot_objects(
                PRODUCT,
                self._get_hubspot_product_structure(unsynced_products),
                site_configuration
            )
            self._upsert_hubspot_objects(
                DEAL,
                self._get_hubspot_deal_structure(unsynced_carts, site_configuration.partner),
                site_configuration
            )
            self._upsert_hubspot_objects(
                LINE_ITEM,
                self._get_hubspot_line_item_structure(unsynced_cart_lines),
                site_configuration
            )
        else:
            self.stdout.write('No data found to sync for site {site}'.format(site=site_configuration.site.domain))

    def add_arguments(self, parser):
        parser.add_argument(
            '--initial-sync-days',
            default=DEFAULT_INITIAL_DAYS,
            dest='initial_sync_days',
            type=int,
            help='Number of days before today to start initial sync',
        )

    def handle(self, *args, **options):
        """
        Main command handler.
        """
        self.initial_sync_days = options['initial_sync_days']
        try:
            site_configurations = self._get_hubspot_enable_sites()
            if not site_configurations:
                self.stdout.write('No Hubspot enabled SiteConfiguration Found.')
                return

            for site_configuration in site_configurations:
                if self._install_hubspot_ecommerce_bridge(site_configuration):
                    if self._define_hubspot_ecommerce_settings(site_configuration):
                        self._sync_data(site_configuration)
                        self._call_sync_errors_messages_endpoint(site_configuration)
        except Exception as ex:
            traceback.print_exc()
            raise CommandError('Command failed with traceback %s' % str(ex))
