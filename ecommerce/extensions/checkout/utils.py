import logging
import requests

from django.conf import settings

from ecommerce.core.url_utils import get_lms_url


logger = logging.getLogger(__name__)


def get_provider_data(provider_id):
    """Get the provider information for provider id provider.

    Args:
        provider_id(str): Identifier for the provider

    Returns: dict
    """
    provider_info_url = get_lms_url('api/credit/v1/providers/{}'.format(provider_id))
    timeout = settings.PROVIDER_DATA_PROCESSING_TIMEOUT
    headers = {
        'Content-Type': 'application/json',
        'X-Edx-Api-Key': settings.EDX_API_KEY
    }
    try:
        response = requests.get(provider_info_url, headers=headers, timeout=timeout)
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(
                'Failed retrieve provider information for %s provider. Provider API returned status code %d. Error: %s',
                provider_id, response.status_code, response.text)
            return None
    except requests.exceptions.ConnectionError:
        logger.exception('Connection error occurred during getting data for %s provider', provider_id)
        return None
    except requests.Timeout:
        logger.exception('Failed to retrieve data for %s provider, connection timeout', provider_id)
        return None
