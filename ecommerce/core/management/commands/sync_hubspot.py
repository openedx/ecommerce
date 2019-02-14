"""
Django management command to Sync Product, Orders and Lines to partners Hubspot server
"""
import logging
import traceback

from django.core.management.base import BaseCommand, CommandError
from oscar.core.loading import get_model

from edx_rest_api_client.client import EdxRestApiClient
from slumber.exceptions import HttpClientError, HttpServerError

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


class Command(BaseCommand):
    help = 'Sync Product, Orders and Lines to partners Hubspot server.'

    def _get_hubspot_enable_sites(self):
        """ Return all SiteConfigurations which have hubspot enabled"""
        return SiteConfiguration.objects.filter(hubspot_secret_key__isnull=False)

    def _install_hubspot_ecommerce_bridge(self, site_conf):
        """
            Installs hubspot bridge for given site_conf
        :param site_conf: SiteConfiguration object
        """
        client = EdxRestApiClient('/'.join([HUBSPOT_API_BASE_URL, 'extensions/ecomm/v1']))
        try:
            client.installs.post(hapikey=site_conf.hubspot_secret_key)
        except (HttpClientError, HttpServerError) as ex:
            message = 'An error occurred while installing hubspot ecommerce bridge for site {domain}, {message}'.format(
                domain=site_conf.site.domain, message=ex.message
            )
            self.stderr.write(message)

    def _define_hubspot_ecommerce_settings(self, site_conf):
        """
          Define hubspot ecommerce setting for given site_conf
        """
        client = EdxRestApiClient('/'.join([HUBSPOT_API_BASE_URL, 'extensions/ecomm/v1']))
        try:
            client.settings.put(HUBSPOT_ECOMMERCE_SETTINGS, hapikey=site_conf.hubspot_secret_key)
        except (HttpClientError, HttpServerError) as ex:
            message = 'An error occurred while defining hubspot ecommerce settings for site {domain}, {message}'.format(
                domain=site_conf.site.domain, message=ex.message
            )
            self.stderr.write(message)

    def handle(self, *args, **options):
        """ Main command handler """
        try:
            site_configs = self._get_hubspot_enable_sites()
            # setting initial configuration before sync

            if not site_configs:
                self.stdout.write('No Hubspot enabled SiteConfiguration Found.')
                return

            for site_conf in site_configs:
                self.stdout.write('Started syncing data of site {site} to Hubspot.'
                                  .format(site=site_conf.site))
                self._install_hubspot_ecommerce_bridge(site_conf)
                self._define_hubspot_ecommerce_settings(site_conf)

        except Exception as ex:
            traceback.print_exc()
            raise CommandError('Command failed with traceback %s' % str(ex))
