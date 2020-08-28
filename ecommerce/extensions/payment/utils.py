# Changes part of REV-1209 - see https://github.com/edx/ecommerce/pull/3020
import copy
import logging
import os
import re
from urllib.parse import urlencode

# Changes part of REV-1209 - see https://github.com/edx/ecommerce/pull/3020
import crum
import requests
# Changes part of REV-1209 - see https://github.com/edx/ecommerce/pull/3020
import waffle
from django.conf import settings
from django.contrib.auth import logout
from django.utils.translation import ugettext_lazy as _
from oscar.core.loading import get_model
from requests.exceptions import HTTPError, Timeout

from ecommerce.core.constants import SEAT_PRODUCT_CLASS_NAME
from ecommerce.extensions.analytics.utils import parse_tracking_context
from ecommerce.extensions.payment.models import SDNCheckFailure

logger = logging.getLogger(__name__)
Basket = get_model('basket', 'Basket')
BasketAttribute = get_model('basket', 'BasketAttribute')
BasketAttributeType = get_model('basket', 'BasketAttributeType')


def get_basket_program_uuid(basket):
    """
    Return the program UUID associated with the given basket, if one exists.
    Arguments:
        basket (Basket): The basket object.
    Returns:
        string: The program UUID if the basket is associated with a bundled purchase, otherwise None.
    """
    try:
        attribute_type = BasketAttributeType.objects.get(name='bundle_identifier')
    except BasketAttributeType.DoesNotExist:
        return None
    bundle_attributes = BasketAttribute.objects.filter(
        basket=basket,
        attribute_type=attribute_type
    )
    bundle_attribute = bundle_attributes.first()
    return bundle_attribute.value_text if bundle_attribute else None


def get_program_uuid(order):
    """
    Return the program UUID associated with the given order, if one exists.

    Arguments:
        order (Order): The order object.

    Returns:
        string: The program UUID if the order is associated with a bundled purchase, otherwise None.
    """
    return get_basket_program_uuid(order.basket)


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

    slice_size = (chars - indicator_length) // 2
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
        request : The current request
        products (list): A list of products to check access against

    Returns:
        Bool
    """
    courses = []
    _, _, ip = parse_tracking_context(user, usage='embargo')

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


def checkSDN(request, name, city, country):
    """
    Performs an SDN check and returns hits of the user failures.
    """
    hit_count = 0

    site_configuration = request.site.siteconfiguration
    basket = Basket.get_basket(request.user, site_configuration.site)

    if site_configuration.enable_sdn_check:
        sdn_check = SDNClient(
            api_url=settings.SDN_CHECK_API_URL,
            api_key=settings.SDN_CHECK_API_KEY,
            sdn_list=site_configuration.sdn_api_list
        )
        try:
            response = sdn_check.search(name, city, country)
            hit_count = response['total']
            if hit_count > 0:
                sdn_check.deactivate_user(
                    basket,
                    name,
                    city,
                    country,
                    response
                )
                logout(request)
        except (HTTPError, Timeout):
            # If the SDN API endpoint is down or times out
            # the user is allowed to make the purchase.
            pass

    return hit_count


def download_SDN_fallback_csv():
    """ Downloads csv for use as fallback for SDN check.'
    """
    url = 'http://api.trade.gov/static/consolidated_screening_list/consolidated.csv'
    csv_file_name = 'temp_sdn_fallback.csv'

    with requests.Session() as s:
        download = s.get(url)

    csv = open(csv_file_name, 'wb')
    csv.write(download.content)
    csv.close()
    file_size_in_bytes = os.path.getsize(csv_file_name)
    file_size_in_MB = file_size_in_bytes / 10**6

    return csv, file_size_in_MB, csv_file_name


class SDNClient:
    """A utility class that handles SDN related operations."""
    def __init__(self, api_url, api_key, sdn_list):
        self.api_url = api_url
        self.api_key = api_key
        self.sdn_list = sdn_list

    # Changes part of REV-1209 - see https://github.com/edx/ecommerce/pull/3020
    def make_testing_sdn_call(self, auth_header, first_check_response, params_dict):  # pragma: no cover
        """
        This is temporary code added as part of REV-1209.
        The intent of this code is to compare the results of the SDN check
        with fuzzy matching turned on and off.
        Logs are included to help inform whether a threshold should be set
        for the score that is included with the fuzzy match query results.
        """
        try:
            if waffle.flag_is_active(crum.get_current_request(), 'make_second_sdn_check'):
                second_check_dict = copy.deepcopy(params_dict)
                first_check_results = first_check_response.json().get("results", [])
                second_check_dict['fuzzy_name'] = 'true'
                second_check_params = urlencode(second_check_dict)
                sdn_check_url = '{api_url}?{params}'.format(
                    api_url=self.api_url,
                    params=second_check_params
                )
                second_check_response = requests.get(
                    sdn_check_url,
                    headers=auth_header,
                    timeout=settings.SDN_CHECK_REQUEST_TIMEOUT
                )
                if second_check_response.status_code != 200:
                    logger.warning(
                        'Fuzzy SDN check error: status code [%d] message: [%s]',
                        second_check_response.status_code, second_check_response.content
                    )
                second_check_results = second_check_response.json().get("results", [])
                if second_check_results:
                    top_score = max(r.get("score", -1) for r in second_check_results)
                    if first_check_results:
                        logger.info(
                            'Regular SDN check: match. Fuzzy SDN check: match. Fuzzy match top score: [%s]',
                            top_score
                        )
                    else:
                        logger.info(
                            'Regular SDN check: no match. Fuzzy SDN check: match. Fuzzy match top score: [%s]',
                            top_score
                        )
                elif first_check_results:
                    logger.info('Regular SDN check: match. Fuzzy SDN check: no match.')
        except Exception as e:  # pylint:disable=broad-except
            # Since this code is purely for testing purposes,
            # we ensure any error would not interfere with the actual transaction.
            logger.warning("Fuzzy SDN check error [%s]", str(e))

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
        # Changes part of REV-1209 - see https://github.com/edx/ecommerce/pull/3020
        params_dict = {
            'sources': self.sdn_list,
            'type': 'individual',
            'name': str(name).encode('utf-8'),
            # We are using the city as the address parameter value as indicated in the documentation:
            # http://developer.trade.gov/consolidated-screening-list.html
            'address': str(city).encode('utf-8'),
            'countries': country
        }
        params = urlencode(params_dict)
        sdn_check_url = '{api_url}?{params}'.format(
            api_url=self.api_url,
            params=params
        )
        auth_header = {'Authorization': 'Bearer {}'.format(self.api_key)}

        try:
            response = requests.get(
                sdn_check_url,
                headers=auth_header,
                timeout=settings.SDN_CHECK_REQUEST_TIMEOUT
            )
        except requests.exceptions.Timeout:
            logger.warning('Connection to US Treasury SDN API timed out for [%s].', name)
            raise

        # Changes part of REV-1209 - see https://github.com/edx/ecommerce/pull/3020
        self.make_testing_sdn_call(auth_header, response, params_dict)  # pragma: no cover

        if response.status_code != 200:
            logger.warning(
                'Unable to connect to US Treasury SDN API for [%s]. Status code [%d] with message: [%s]',
                name, response.status_code, response.content
            )
            raise requests.exceptions.HTTPError('Unable to connect to SDN API')

        return response.json()

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
