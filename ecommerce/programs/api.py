import logging

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class ProgramsApiClient(object):
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

        program = cache.get(cache_key)

        if program:  # pragma: no cover
            logger.debug('Program [%s] was found in the cache.', program_uuid)
        else:
            logging.info('Retrieving details of of program [%s]...', program_uuid)
            program = self.client.programs(program_uuid).get()
            cache.set(cache_key, program, self.cache_ttl)
            logging.info('Program [%s] was successfully retrieved and cached.', program_uuid)

        return program
