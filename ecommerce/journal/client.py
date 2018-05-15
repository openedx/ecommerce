"""
Utility Functions to Access the Discovery Journal API and the Journals Service API
"""
import logging

from django.core.cache import cache
from edx_rest_api_client.client import EdxRestApiClient

from ecommerce.core.utils import get_cache_key
from ecommerce.journal.constants import JOURNAL_BUNDLE_CACHE_TIMEOUT

logger = logging.getLogger(__name__)


def get_journals_service_client(site_configuration):
    """
    Returns Journals Service client
    """
    return EdxRestApiClient(
        site_configuration.journals_api_url,
        jwt=site_configuration.access_token
    )


def post_journal_access(site_configuration, order_number, username, journal_uuid):
    """
    Send POST request to journal access api

    Args:
        site_configuration (SiteConfiguration): site configuration
        order_number (str): number of order access was purchased in
        username (str): username of user purchasing access to journal
        journal_uuid (str): uuid of journal being accessed

    Returns:
        response
    """
    client = get_journals_service_client(site_configuration)
    data = {
        'order_number': order_number,
        'user': username,
        'journal': journal_uuid
    }
    return client.journalaccess.post(data)


def fetch_journal_bundle(site, journal_bundle_uuid):
    """
    Retrieve journal bundle for given uuid.
    Retrieve it from cache if present, otherwise send GET request to journal bundle
        discovery api and store in cache.

    Args:
        site
        journal_bundle_uuid (str): uuid for desired journal bundle

    Returns:
        (dict): contains dict of journal_bundle attributes

    Raises:
        ConnectionError: raised if ecommerce is unable to connect to enterprise api server.
        SlumberBaseException: raised if API response contains http error status like 4xx, 5xx etc...
        Timeout: request is raised if API is taking too long to respond
    """

    api_resource = 'journal_bundle'
    cache_key = get_cache_key(
        site_domain=site.domain,
        resource=api_resource,
        journal_bundle_uuid=journal_bundle_uuid
    )

    journal_bundle = cache.get(cache_key)
    if not journal_bundle:
        client = site.siteconfiguration.journal_discovery_api_client
        journal_bundle = client.journal_bundles(journal_bundle_uuid).get()
        cache.set(cache_key, journal_bundle, JOURNAL_BUNDLE_CACHE_TIMEOUT)

    return journal_bundle
