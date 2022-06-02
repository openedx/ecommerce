

import logging
from urllib.parse import urljoin

from django.conf import settings
from edx_django_utils.cache import TieredCache

logger = logging.getLogger(__name__)


class ProgramsApiClient:
    """ Client for the Programs API.

    This client is designed to cache the data retrieved from the Programs API to
    reduce load on the API and increase performance of consuming services.
    """

    def __init__(self, site_config):
        self.cache_ttl = settings.PROGRAM_CACHE_TIMEOUT
        self.client = site_config.oauth_api_client
        self.api_url = site_config.discovery_api_url
        self.site_domain = site_config.site.domain

    def get_program(self, uuid):
        """
        Retrieve the details for a single program.

        Args:
            uuid (str|uuid): Program UUID.

        Returns:
            dict
        """
        program_uuid = str(uuid)
        cache_key = '{site_domain}-program-{uuid}'.format(site_domain=self.site_domain, uuid=program_uuid)

        program_cached_response = TieredCache.get_cached_response(cache_key)

        if program_cached_response.is_found:  # pragma: no cover
            logger.debug('Program [%s] was found in the cache.', program_uuid)
            return program_cached_response.value

        logging.info('Retrieving details of program [%s]...', program_uuid)
        api_url = urljoin(f"{self.api_url}/", f"programs/{program_uuid}/")
        resp = self.client.get(api_url)
        resp.raise_for_status()
        program = resp.json()

        TieredCache.set_all_tiers(cache_key, program, self.cache_ttl)
        logging.info('Program [%s] was successfully retrieved and cached.', program_uuid)
        return program
