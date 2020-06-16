

import logging

from requests.exceptions import ConnectionError as ReqConnectionError
from requests.exceptions import Timeout
from slumber.exceptions import HttpNotFoundError, SlumberBaseException

from ecommerce.programs.api import ProgramsApiClient

log = logging.getLogger(__name__)


def get_program(program_uuid, siteconfiguration):
    """
    Returns details for the program identified by the program_uuid.

    Data is retrieved from the Discovery Service, and cached for ``settings.PROGRAM_CACHE_TIMEOUT`` seconds.

    Args:
        siteconfiguration (SiteConfiguration): Configuration containing the requisite parameters
            to connect to the Discovery Service.

        program_uuid (uuid): id to query the specified program

    Returns:
        dict
        None if not found or another error occurs
    """
    response = None
    try:
        client = ProgramsApiClient(siteconfiguration.discovery_api_client, siteconfiguration.site.domain)
        response = client.get_program(str(program_uuid))
    except HttpNotFoundError:
        msg = 'No program data found for {}'.format(program_uuid)
        log.debug(msg)
    except (ReqConnectionError, SlumberBaseException, Timeout):
        msg = 'Failed to retrieve program details for {}'.format(program_uuid)
        log.debug(msg)

    return response
