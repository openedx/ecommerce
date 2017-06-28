import json
import logging
import re
from urllib import urlencode

import requests
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from oscar.core.loading import get_model

from ecommerce.core.constants import SEAT_PRODUCT_CLASS_NAME
from ecommerce.extensions.analytics.utils import parse_tracking_context
from ecommerce.extensions.payment.models import SDNCheckFailure

logger = logging.getLogger(__name__)
Basket = get_model('basket', 'Basket')


def middle_truncate(string, chars):
    """Truncate the provided string, if necessary.

    Cuts excess characters from the middle of the string and replaces
    them with a string indicating that truncation has occurred.

    Arguments:
        string (unicode or str): The string to be truncated.
        chars (int): The character limit for the truncated string.

    Returns:
        Unicode: The truncated string, of length less than or equal to `chars`.
            If no truncation was required, the original string is returned.

    Raises:
        ValueError: If the provided character limit is less than the length of
            the truncation indicator.
    """
    if len(string) <= chars:
        return string

    # Translators: This is a string placed in the middle of a truncated string
    # to indicate that truncation has occurred. For example, if a title may only
    # be at most 11 characters long, "A Very Long Title" (17 characters) would be
    # truncated to "A Ve...itle".
    indicator = _('...')

    indicator_length = len(indicator)
    if chars < indicator_length:
        raise ValueError

    slice_size = (chars - indicator_length) / 2
    start, end = string[:slice_size], string[-slice_size:]
    truncated = u'{start}{indicator}{end}'.format(start=start, indicator=indicator, end=end)

    return truncated


def clean_field_value(value):
    """Strip the value of any special characters.

    Currently strips caret(^), colon(:) and quote(" ') characters from the value.

    Args:
        value (str): The original value.

    Returns:
        A cleaned string.
    """
    return re.sub(r'[\^:"\']', '', value)


def embargo_check(user, site, products):
    """ Checks if the user has access to purchase products by calling the LMS embargo API.

    Args:
        request (object): The current request
        products (list): A list of products to check access against

    Returns:
        Bool
    """
    courses = []
    _, _, ip = parse_tracking_context(user)

    for product in products:
        # We only are checking Seats
        if product.get_product_class().name == SEAT_PRODUCT_CLASS_NAME:
            courses.append(product.course.id)

    if courses:
        params = {
            'user': user,
            'ip_address': ip,
            'course_ids': courses
        }

        try:
            response = site.siteconfiguration.embargo_api_client.course_access.get(**params)
            return response.get('access', True)
        except:  # pylint: disable=bare-except
            # We are going to allow purchase if the API is un-reachable.
            pass

    return True


class SDNClient(object):
    """A utility class that handles SDN related operations."""
    def __init__(self, api_url, api_key, sdn_list):
        self.api_url = api_url
        self.api_key = api_key
        self.sdn_list = sdn_list

    def search(self, name, city, country):
        """
        Searches the OFAC list for an individual with the specified details.
        The check returns zero hits if:
            * request to the SDN API times out
            * SDN API returns a non-200 status code response
            * user is not found on the SDN list

        Args:
            name (str): Individual's full name.
            city (str): Individual's city.
            country (str): ISO 3166-1 alpha-2 country code where the individual is from.
        Returns:
            dict: SDN API response.
        """
        params = urlencode({
            'sources': self.sdn_list,
            'api_key': self.api_key,
            'type': 'individual',
            'name': unicode(name).encode('utf-8'),
            # We are using the city as the address parameter value as indicated in the documentation:
            # http://developer.trade.gov/consolidated-screening-list.html
            'address': unicode(city).encode('utf-8'),
            'countries': country
        })
        sdn_check_url = '{api_url}?{params}'.format(
            api_url=self.api_url,
            params=params
        )

        try:
            response = requests.get(sdn_check_url, timeout=settings.SDN_CHECK_REQUEST_TIMEOUT)
        except requests.exceptions.Timeout:
            logger.warning('Connection to US Treasury SDN API timed out for [%s].', name)
            raise

        if response.status_code != 200:
            logger.warning(
                'Unable to connect to US Treasury SDN API for [%s]. Status code [%d] with message: [%s]',
                name, response.status_code, response.content
            )
            raise requests.exceptions.HTTPError('Unable to connect to SDN API')

        return json.loads(response.content)

    def deactivate_user(self, basket, name, city, country, search_results):
        """ Deactivates a user account.

        Args:
            basket (Basket): The user's basket.
            name (str): The user's name.
            city (str): The user's city.
            country (str): ISO 3166-1 alpha-2 country code where the individual is from.
            search_results (dict): Results from a call to `search` that will
                be recorded as the reason for the deactivation.
        """
        site = basket.site
        snd_failure = SDNCheckFailure.objects.create(
            full_name=name,
            username=basket.owner.username,
            city=city,
            country=country,
            site=site,
            sdn_check_response=search_results
        )
        for line in basket.lines.all():
            snd_failure.products.add(line.product)

        logger.warning('SDN check failed for user [%s] on site [%s]', name, site.name)
        basket.owner.deactivate_account(site.siteconfiguration)
