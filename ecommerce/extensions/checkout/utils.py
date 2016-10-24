import logging
import urllib

from babel.numbers import format_currency
from django.conf import settings
from django.core.urlresolvers import reverse
from django.utils.translation import get_language, to_locale
from edx_rest_api_client.client import EdxRestApiClient
from requests.exceptions import ConnectionError, Timeout
from slumber.exceptions import SlumberHttpBaseException


logger = logging.getLogger(__name__)


def get_credit_provider_details(access_token, credit_provider_id, site_configuration):
    """ Returns the credit provider details from LMS.

    Args:
        access_token (str): JWT access token
        credit_provider_id (str): Identifier for the provider
        site_configuration (SiteConfiguration): Ecommerce Site Configuration

    Returns: dict
    """
    try:
        return EdxRestApiClient(
            site_configuration.build_lms_url('api/credit/v1/'),
            oauth_access_token=access_token
        ).providers(credit_provider_id).get()
    except (ConnectionError, SlumberHttpBaseException, Timeout):
        logger.exception('Failed to retrieve credit provider details for provider [%s].', credit_provider_id)
        return None


def get_receipt_page_url(site_configuration, order_number=None):
    """ Returns the receipt page URL.

    Args:
        order_number (str): Order number
        site_configuration (SiteConfiguration): Site Configuration containing the flag for enabling Otto receipt page.

    Returns:
        str: Receipt page URL.
    """
    if site_configuration.enable_otto_receipt_page:
        base_url = site_configuration.build_ecommerce_url(reverse('checkout:receipt'))
        params = urllib.urlencode({'order_number': order_number}) if order_number else ''
    else:
        base_url = site_configuration.build_lms_url('/commerce/checkout/receipt')
        params = urllib.urlencode({'orderNum': order_number}) if order_number else ''

    return '{base_url}{params}'.format(
        base_url=base_url,
        params='?{params}'.format(params=params) if params else ''
    )


def add_currency(amount):
    """ Adds currency to the price amount.

    Args:
        amount (Decimal): Price amount

    Returns:
        str: Formatted price with currency.
    """
    return format_currency(
        amount,
        settings.OSCAR_DEFAULT_CURRENCY,
        format=u'#,##0.00',
        locale=to_locale(get_language())
    )
