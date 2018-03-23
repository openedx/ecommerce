from edx_rest_api_client.client import EdxRestApiClient


def get_journals_service_client(site_configuration):
    """
    Returns Journals Service client
    """
    #TODO: add access tokens
    # return EdxRestApiClient(site_configuration.journals_api_url, jwt=site_configuration.access_token())
    return EdxRestApiClient(site_configuration.journals_api_url)


def post_journal_access(site_configuration, order_number, username, journal_uuid):
    """
    Send POST request to journal access api

    Args:
        order_number (str): number of order access was purchased in
        username (str): username of user purchasing access to journal
        journal_uuid (str): uuid of journal being accessed

    Returns:
        response
    """
    # TODO: add response type in docs
    client = get_journals_service_client(site_configuration=site_configuration)
    data = {
        'order_number': order_number,
        'user': username,
        'journal': journal_uuid
    }
    return client.journalaccess.post(data)


