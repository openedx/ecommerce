from requests.exceptions import  ConnectionError, Timeout
from slumber.exceptions import HttpNotFoundError, SlumberBaseException

from ecommerce.digital_books.api import DigitalBookApiClient

import logging
log = logging.getLogger(__name__)


def get_digital_book_bundle(digital_book_bundle_uuid, site_configuration):
    """
    Returns details for the digital book bundle identified by the digital_book_bundle_uuid

    #TODO: what is this?
    Data is retried from the Discovery Service and cached for ``settings.DIGITAL_BOOK_BUNDLE_CACHE_TIMEOUT``

    Args:
        digital_book_bundle_uuid (uuid): id to query the specified digital book bundle

        site_configuration (SiteConfiguration): Configuration containing the requisite parameters
            to connect to the Discovery Service

    Returns:
        dict
        None if not found or another error occurs
    """
    response = None
    try:
        client = DigitalBookApiClient(site_configuration.discovery_api_client, site_configuration.site.domain)
        response = client.get_digital_book_bundle(str(digital_book_bundle_uuid))
    except HttpNotFoundError:
        msg = 'No digital book bundle data found for {}'.format(digital_book_bundle_uuid)
        log.debug(msg)
    except (ConnectionError, SlumberBaseException, Timeout):
        msg = 'Failed to retrieve digital book bundle details for {}'.format(digital_book_bundle_uuid)
        log.debug(msg)

    return response
