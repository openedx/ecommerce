

import logging
from urllib import parse

from babel.numbers import format_currency as default_format_currency
from django.conf import settings
from django.urls import reverse
from django.utils.translation import get_language, to_locale
from requests.exceptions import ConnectionError as ReqConnectionError
from requests.exceptions import Timeout
from slumber.exceptions import SlumberHttpBaseException

logger = logging.getLogger(__name__)


def get_credit_provider_details(credit_provider_id, site_configuration):
    """ Returns the credit provider details from LMS.

    Args:
        credit_provider_id (str): Identifier for the provider
        site_configuration (SiteConfiguration): Ecommerce Site Configuration

    Returns: dict
    """
    try:
        return site_configuration.credit_api_client.providers(credit_provider_id).get()
    except (ReqConnectionError, SlumberHttpBaseException, Timeout):
        logger.exception('Failed to retrieve credit provider details for provider [%s].', credit_provider_id)
        return None


def get_receipt_page_url(site_configuration, order_number=None, override_url=None, disable_back_button=False):
    """ Returns the receipt page URL.

    Args:
        order_number (str): Order number
        site_configuration (SiteConfiguration): Site Configuration containing the flag for enabling Otto receipt page.
        override_url (str): New receipt page to override the default one.
        disable_back_button (bool): Whether to disable the back button from receipt page. Defaults to false as the
            receipt page is referenced in emails/etc., and we only want to disable the back button from the receipt
            page if the user has gone through the payment flow.

    Returns:
        str: Receipt page URL.
    """
    if override_url:
        return override_url

    url_params = {}
    if order_number:
        url_params['order_number'] = order_number
    if disable_back_button:
        url_params['disable_back_button'] = int(disable_back_button)
    base_url = site_configuration.build_ecommerce_url(reverse('checkout:receipt'))
    params = parse.urlencode(url_params)

    return '{base_url}{params}'.format(
        base_url=base_url,
        params='?{params}'.format(params=params) if params else ''
    )


def format_currency(currency, amount, format=None, locale=None):  # pylint: disable=redefined-builtin
    locale = locale or to_locale(get_language())
    format = format or getattr(settings, 'OSCAR_CURRENCY_FORMAT', None)

    return default_format_currency(
        amount,
        currency,
        format=format,
        locale=locale
    )


def add_currency(amount):
    """ Adds currency to the price amount.

    Args:
        amount (Decimal): Price amount

    Returns:
        str: Formatted price with currency.
    """
    return format_currency(settings.OSCAR_DEFAULT_CURRENCY, amount, u'#,##0.00')
