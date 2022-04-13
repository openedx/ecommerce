

import logging

from requests.exceptions import ConnectionError as ReqConnectionError
from requests.exceptions import HTTPError, Timeout

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
        client = ProgramsApiClient(siteconfiguration)
        response = client.get_program(str(program_uuid))
    except (ReqConnectionError, HTTPError, Timeout):
        log.debug("Failed to retrieve program details for %s", program_uuid)

    return response
