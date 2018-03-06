from django.conf import settings
from django.core.cache import cache

import logging
logger = logging.getLogger(__name__)


class DigitalBookApiClient(object):
    """ Client for the Digital Book Bundle API

    This client is designed to cache the data retrieved from the Digital Book Bundle API o
    reduce load on the API and increase performance of consuming services.
    """

    def __init__(self, client, site_domain):
        self.cache_ttl = settings.DIGITAL_BOOK_BUNDLE_TIMEOUT
        self.client = client
        self.site_domain = site_domain

    def get_digital_book_bundle(self, uuid):
        """
        Retrieve the details for a single digital book bundle.

        Args:
            uuid (str|uuid): Digital Book Bundle

        Returns:
            dict
        """

        digital_book_bundle_uuid = str(uuid)
        cache_key = '{site_domain}-digital-book-bundle-{uuid}'.format(
            site_domain=self.site_domain,
            uuid=digital_book_bundle_uuid
        )

        digital_book_bundle = cache.get(cache_key)

        if digital_book_bundle:
            #TODO: change this to debug log instead of info log
            # logger.debug('Digital Book Bundle [%s] was found in the cache', digital_book_bundle_uuid)
            logger.info('>>> Digital Book Bundle [%s] was found in the cache', digital_book_bundle_uuid)
        else:
            logging.info('Retrieving details of digital book bundle [%s]...', digital_book_bundle_uuid)
            #TODO: add digital book bundle to discovery
            digital_book_bundle = self.client.digital_book_bundles(digital_book_bundle_uuid).get()
            cache.set(cache_key, digital_book_bundle, self.cache_ttl)
            logging.info('Digital Book Bundle [%s] was successfully retrieved and cached.', digital_book_bundle_uuid)

        return digital_book_bundle