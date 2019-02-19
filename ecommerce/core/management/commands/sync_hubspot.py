"""
Django management command to Sync Product, Orders and Lines to partners Hubspot server
"""
import logging
import time
import traceback
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from edx_rest_api_client.client import EdxRestApiClient
from oscar.core.loading import get_model
from slumber.exceptions import HttpClientError, HttpServerError

from ecommerce.extensions.fulfillment.status import ORDER

Order = get_model('order', 'Order')
OrderLine = get_model('order', 'Line')
Product = get_model('catalogue', 'Product')
SiteConfiguration = get_model('core', 'SiteConfiguration')
logger = logging.getLogger(__name__)


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
                'propertyName': 'number',
                'dataType': 'STRING',
                'targetHubspotProperty': 'ip__ecomm_bridge__order_number'
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
ORDER_STATUS = {
    ORDER.OPEN: "checkout_completed",
    ORDER.FULFILLMENT_ERROR: "cancelled",
    ORDER.COMPLETE: "processed"
}
PRODUCT = "PRODUCT"
LINE_ITEM = "LINE_ITEM"
DEAL = "DEAL"
BATCH_SIZE = 200


class Command(BaseCommand):
    help = 'Sync Product, Orders and Lines to partners Hubspot server.'

    def _get_hubspot_enable_sites(self):
        """
        Returns all SiteConfigurations which have hubspot enabled
        """
        return SiteConfiguration.objects.filter(hubspot_secret_key__isnull=False)

    def _hubspot_endpoint(self, api, api_url, api_type, body=None, **kwargs):
        """
        This function is responsible for all the calls of hubspot.
        """
        client = EdxRestApiClient('/'.join([HUBSPOT_API_BASE_URL, api_url]))
        if api_type == "GET":
            return getattr(client, api).get(**kwargs)
        if api_type == "POST":
            return getattr(client, api).post(**kwargs)
        if api_type == "PUT":
            return getattr(client, api).put(body, **kwargs)

    def _install_hubspot_ecommerce_bridge(self, site_configuration):
        """
        Installs hubspot bridge for given site_configuration
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
                    site=site_configuration.site.domain, message=ex.message
                )
            )
        return status

    def _define_hubspot_ecommerce_settings(self, site_configuration):
        """
        Define hubspot ecommerce setting for given site_configuration
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
                    site=site_configuration.site.domain, message=ex.message
                )
            )
        return status

    def _get_hubspot_deal_structure(self, orders):
        """
        Returns list of dicts, each dict represents hubspot DEAL.
        """
        hubspot_orders = []
        for order in orders:
            hubspot_orders.append({
                'integratorObjectId': str(order.id),
                'action': 'UPSERT',
                'changeOccurredTimestamp': int(time.time()),
                'propertyNameToValues': {
                    'total_incl_tax': str(order.total_incl_tax),
                    'checkout_status': ORDER_STATUS[order.status],
                    'date_placed': int(
                        (order.date_placed - datetime(1970, 1, 1, tzinfo=order.date_placed.tzinfo)).total_seconds()
                    ),
                    'number': order.number
                }
            })
        return hubspot_orders

    def _get_hubspot_line_item_structure(self, lines):
        """
        Returns list of dicts, each dict represents hubspot LINE_ITEM.
        """
        hubspot_line_items = []
        for line in lines:
            hubspot_line_items.append({
                'integratorObjectId': str(line.id),
                'action': 'UPSERT',
                'changeOccurredTimestamp': int(time.time()),
                'propertyNameToValues': {
                    'order_id': str(line.order.id),
                    'price_currency': str(line.order.currency),
                    'tax': str(line.line_price_incl_tax - line.line_price_excl_tax),
                    'product_id': str(line.product.id),
                    'price_incl_tax': str(line.line_price_incl_tax),
                    'price_excl_tax': str(line.line_price_excl_tax),
                    'quantity': line.quantity
                }
            })
        return hubspot_line_items

    def _get_hubspot_product_structure(self, products):
        """
        Returns list of dicts, each dict represents hubspot PRODUCT.
        """
        hubspot_products = []
        unique_product_ids = []
        for product in products:
            if product.id not in unique_product_ids:
                hubspot_products.append({
                    'integratorObjectId': str(product.id),
                    'action': 'UPSERT',
                    'changeOccurredTimestamp': int(time.time()),
                    'propertyNameToValues': {
                        'title': str(product.title),
                        'description': str(product.description)
                    }
                })
                unique_product_ids.append(product.id)
        return hubspot_products

    def _upsert_hubspot_objects(self, object_type, objects, site_configuration):
        """
        Calls the sync message endpoint on given objects (PRODUCT, DEAL and LINE_ITEM)
        and each request can has 200 (BATCH_SIZE) objects.
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
                    object_type=object_type, site=site_configuration.site.domain, message=ex.message
                )
            )

    def _call_sync_errors_messages_endpoint(self, site_configuration):
        """
        Calls the sync error endpoint and print the response
        """
        try:
            response = self._hubspot_endpoint(
                'sync-errors',
                'extensions/ecomm/v1/',
                'GET',
                hapikey=site_configuration.hubspot_secret_key
            )
            for error in response.get('results'):
                self.stderr.write(
                    'sync-error endpoint: for {object_type} with id {id} for site {site}: {message}'.format(
                        object_type=error.get('objectType'),
                        id=error.get('integratorObjectId'),
                        site=site_configuration.site.domain,
                        message=error.get('details')
                    )
                )
        except (HttpClientError, HttpServerError) as ex:
            self.stderr.write(
                'An error occurred while getting the syncing message for site {site}: {message} '.format(
                    site=site_configuration.site.domain, message=ex.message
                )
            )

    def _get_last_synced_order(self, site_configuration):
        """
        Calls the deal/recent/modified hubspot endpoint
        then returns the Order object for that deal.
        """
        last_synced_order = None
        try:
            response = self._hubspot_endpoint(
                'modified',
                'deals/v1/deal/recent/',
                'GET',
                hapikey=site_configuration.hubspot_secret_key,
                count=1
            )
            if response.get('results'):
                number = response.get('results')[0].get('properties').get('ip__ecomm_bridge__order_number').get('value')
                last_synced_order = Order.objects.filter(number=number).first()
                self.stdout.write(
                    "Successfully fetched last sync DEAl with order_number: {number}".format(
                        number=number
                    )
                )
        except (HttpClientError, HttpServerError) as ex:
            self.stderr.write(
                'An error occurred while fetching the last synced deal for site {site}, {message}'.format(
                    site=site_configuration.site.domain, message=ex.message
                )
            )
        return last_synced_order

    def _get_unsynced_orders(self, site_configuration):
        """
        Returns the list of orders which are not synced with hubspot.
        If it is first syncing call then it will return the orders
        that has lesser date_placed than current datetime.now().
        else it will return all the orders that has greater date_place
        value than last sync_order's date_placed.
        """
        orders = Order.objects.filter(site=site_configuration.site)
        last_synced_order = self._get_last_synced_order(site_configuration)
        if last_synced_order:
            orders = orders.filter(date_placed__gt=last_synced_order.date_placed)
            if orders:
                self.stdout.write(
                    'Pulled unsynced orders for site {site} from {last_sync}'.format(
                        site=site_configuration.site.domain, last_sync=last_synced_order.date_placed
                    )
                )
        else:
            orders = orders.filter(date_placed__lte=datetime.now())
            self.stdout.write(
                'It is first syncing call, it will pull all the orders for syncing for site {site}'.format(
                    site=site_configuration.site.domain
                )
            )
        return orders

    def _sync_data(self, site_configuration):
        """
        Create lists of Order, OrderLine and Product objects and
        call upsert(PUT) sync-messages endpoint for each objects.
        """
        unsynced_orders = self._get_unsynced_orders(site_configuration)
        if unsynced_orders:
            unsynced_order_lines = OrderLine.objects.filter(order__in=unsynced_orders)
            unsynced_products = Product.objects.filter(line__in=unsynced_order_lines)
            self._upsert_hubspot_objects(
                PRODUCT,
                self._get_hubspot_product_structure(unsynced_products),
                site_configuration
            )
            self._upsert_hubspot_objects(
                DEAL,
                self._get_hubspot_deal_structure(unsynced_orders),
                site_configuration
            )
            self._upsert_hubspot_objects(
                LINE_ITEM,
                self._get_hubspot_line_item_structure(unsynced_order_lines),
                site_configuration
            )
        else:
            self.stdout.write('No data found to sync for site {site}'.format(site=site_configuration.site.domain))

    def handle(self, *args, **options):
        """ Main command handler """
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
