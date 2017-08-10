from ecommerce.programs.api import ProgramsApiClient


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
    """
    client = ProgramsApiClient(siteconfiguration.discovery_api_client, siteconfiguration.site.domain)
    return client.get_program(str(program_uuid))
