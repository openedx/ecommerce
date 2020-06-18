

import logging

from django.conf import settings
from edx_django_utils.cache import TieredCache

logger = logging.getLogger(__name__)


class ProgramsApiClient:
    """ Client for the Programs API.

    This client is designed to cache the data retrieved from the Programs API to
    reduce load on the API and increase performance of consuming services.
    """

    def __init__(self, client, site_domain):
        self.cache_ttl = settings.PROGRAM_CACHE_TIMEOUT
        self.client = client
        self.site_domain = site_domain

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

        logging.info('Retrieving details of of program [%s]...', program_uuid)
        program = self.client.programs(program_uuid).get()

        TieredCache.set_all_tiers(cache_key, program, self.cache_ttl)
        logging.info('Program [%s] was successfully retrieved and cached.', program_uuid)
        return program
