"""
Management command for assigning enterprise roles to existing enterprise users.
"""
from __future__ import absolute_import, unicode_literals

import datetime
import logging

import requests
from django.core.management.base import BaseCommand
from django.utils.timezone import now
from edx_rest_api_client.client import EdxRestApiClient
from oscar.core.loading import get_model

from ecommerce.core.constants import ENROLLMENT_CODE_PRODUCT_CLASS_NAME
from ecommerce.core.models import SiteConfiguration
from ecommerce.invoice.models import Invoice

Category = get_model('catalogue', 'Category')
Benefit = get_model('offer', 'Benefit')
Voucher = get_model('voucher', 'Voucher')

LOGGER = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Management command for populating Ecommerce with an enterprise coupon

    Example usage:
        $ ./manage.py seed_enterprise_devstack_data
    """
    coupon = None
    site = None
    headers = {}
    enterprise_customer = None
    enterprise_catalog = None
    help = 'Seeds an enterprise coupon for an existing enterprise customer.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--enterprise-customer',
            action='store',
            dest='enterprise_customer',
            default=0,
            help='UUID of an existing enterprise customer.',
            type=str,
        )

    def _get_access_token(self):
        """ Returns an access token and expiration date from the OAuth provider.

        Returns:
            (str, datetime)
        """
        LOGGER.info('\nFetching access token for site...')
        oauth2_provider_url = self.site.oauth_settings.get('SOCIAL_AUTH_EDX_OIDC_URL_ROOT')
        key = self.site.oauth_settings.get('BACKEND_SERVICE_EDX_OAUTH2_KEY')
        secret = self.site.oauth_settings.get('BACKEND_SERVICE_EDX_OAUTH2_SECRET')
        oauth_access_token_url = oauth2_provider_url + '/access_token/'
        return EdxRestApiClient.get_oauth_access_token(
            oauth_access_token_url, key, secret, token_type='jwt'
        )

    def _get_default_site(self):
        """ Returns the default site configuration """
        if not self.site:
            self.site = SiteConfiguration.objects.first()
        return self.site

    def _get_headers(self):
        """
        Returns a headers dict containing the authenticated JWT access token
        """
        if not self.headers:
            access_token, __ = self._get_access_token()
            self.headers = {'Authorization': 'JWT ' + access_token}
        return self.headers

    def _get_enterprise_customer(self, url, enterprise_customer_uuid):
        """ Returns an enterprise customer """
        LOGGER.info('\nFetching an enterprise customer...')
        try:
            response = requests.get(
                url,
                params={'uuid': enterprise_customer_uuid} if enterprise_customer_uuid else None,
                headers=self.headers,
            )
            self.enterprise_customer = response.json().get('results')[0]
            return self.enterprise_customer
        except IndexError:
            LOGGER.error('No enterprise customer found.')
            return None

    def _get_enterprise_catalog(self, url):
        """
        Returns a catalog associated with a specified enterprise customer
        """
        if not self.enterprise_customer:
            LOGGER.error('An enterprise customer was not specified.')
            return None
    
        LOGGER.info('\nFetching catalog for enterprise customer (%s)...', self.enterprise_customer.get('uuid'))
        try:
            response = requests.get(
                url,
                params={'enterprise_customer': self.enterprise_customer.get('uuid')},
                headers=self.headers,
            )
            self.enterprise_catalog = response.json().get('results')[0]
            return self.enterprise_catalog
        except IndexError:
            LOGGER.error('No catalog found for enterprise (%s)', self.enterprise_customer.get('uuid'))
            return None

    def _create_coupon(self, url, ecommerce_api_url):
        """
        Creates and returns a coupon associated with the specified
        enterprise customer and catalog
        """
        if not self.enterprise_customer or not self.enterprise_catalog:
            LOGGER.error('An enterprise customer and/or catalog was not specified.')
            return None

        LOGGER.info('\nCreating an enterprise coupon...')
        category = Category.objects.get(slug='bulk-enrollment-upon-redemption')
        request_obj = {
            "category": {
                "id": category.id,
                "name": category.name,
            },
            "code": "",
            "id": None,
            "price": 0,
            "quantity": 1,
            "enterprise_catalog_url": ecommerce_api_url + '/enterprise/customer_catalogs/',
            "coupon_type": ENROLLMENT_CODE_PRODUCT_CLASS_NAME,
            "voucher_type": Voucher.MULTI_USE,
            "benefit_type": Benefit.PERCENTAGE,
            "catalog_type": "Single course",
            "invoice_discount_type": Invoice.PERCENTAGE,
            "invoice_type": Invoice.POSTPAID,
            "tax_deduction": "No",
            "title": "Test Enterprise Coupon 1",
            "enterprise_customer": {
                'id': self.enterprise_customer.get('uuid'),
                'name': self.enterprise_customer.get('name'),
            },
            "enterprise_customer_catalog": self.enterprise_catalog.get('uuid'),
            "start_date": str(now() - datetime.timedelta(days=10)),
            "end_date": str(now() + datetime.timedelta(days=10)),
            "max_uses": 10,
            "invoice_number": "",
            "invoice_payment_date": None,
            "invoice_discount_value": 100,
            "start_datetime": str(now() - datetime.timedelta(days=10)),
            "end_datetime": str(now() + datetime.timedelta(days=10)),
            "benefit_value": 100
        }
        response = requests.post(url, json=request_obj, headers=self.headers)
        self.coupon = response.json()
        return self.coupon

    def handle(self, *args, **options):
        """
        Entry point for managment command execution.
        """
        site = self._get_default_site()
        enterprise_customer_uuid = options['enterprise_customer']

        ecommerce_api_url = site.build_ecommerce_url() + '/api/v2'
        enterprise_api_url = site.enterprise_api_url

        enterprise_customer_request_url = enterprise_api_url + 'enterprise-customer/'
        enterprise_catalog_request_url = enterprise_api_url + 'enterprise_catalogs/'
        enterprise_coupons_request_url = ecommerce_api_url + '/enterprise/coupons/'

        # Set up request headers with JWT access token
        self._get_headers()

        # Fetch enterprise customer
        self._get_enterprise_customer(
            url=enterprise_customer_request_url,
            enterprise_customer_uuid=enterprise_customer_uuid,
        )

        if self.enterprise_customer:
            # Fetch enterprise customer catalog
            self._get_enterprise_catalog(url=enterprise_catalog_request_url)

        if self.enterprise_catalog:
            # Create a new enterprise coupon associated with the
            # above enterprise customer/catalog
            self._create_coupon(
                url=enterprise_coupons_request_url,
                ecommerce_api_url=ecommerce_api_url,
            )
            LOGGER.info('\nEnterprise coupon successfully created: %s', self.coupon)
