# Changes part of REV-1209 - see https://github.com/edx/ecommerce/pull/3020
import copy
import csv
import hashlib
import io
import logging
import re
import string
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urlencode

# Changes part of REV-1209 - see https://github.com/edx/ecommerce/pull/3020
import crum
import pycountry
import requests
# Changes part of REV-1209 - see https://github.com/edx/ecommerce/pull/3020
import waffle
from django.conf import settings
from django.contrib.auth import logout
from oscar.core.loading import get_model
from requests.exceptions import HTTPError, Timeout

from ecommerce.extensions.payment.exceptions import SDNFallbackDataEmptyError
from ecommerce.extensions.payment.models import SDNCheckFailure, SDNFallbackData, SDNFallbackMetadata

logger = logging.getLogger(__name__)
Basket = get_model('basket', 'Basket')
BasketAttribute = get_model('basket', 'BasketAttribute')
BasketAttributeType = get_model('basket', 'BasketAttributeType')

COUNTRY_CODES = {country.alpha_2 for country in pycountry.countries}


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
        except (HTTPError, Timeout) as e:
            # If the SDN API endpoint is down or times out
            # checkSDNFallback will be called. If it finds a hit
            # the user will be blocked from making a purchase.
            logger.info(
                'SDNCheck: SDN API call received an error: %s. SDNFallback function called for basket %d.',
                str(e),
                basket.id
            )
            sdn_fallback_hit_count = checkSDNFallback(
                name,
                city,
                country
            )
            response = {'total': sdn_fallback_hit_count}
        hit_count = response['total']
        if hit_count > 0:
            logger.info(
                'SDNCheck received %d hit(s).',
                hit_count
            )
            sdn_check.deactivate_user(
                basket,
                name,
                city,
                country,
                response
            )
            logout(request)

    return hit_count


def checkSDNFallback(name, city, country):
    """
    Performs an SDN check against the SDNFallbackData

    First, filter the SDNFallbackData records by source, type and country.
    Then, compare the provided name/city against each record and return whether we find a match.
    The check uses the following properties:
        1. Order of words doesn’t matter
        2. Number of times that a given word appears doesn’t matter
        3. Punctuation between words or at the beginning/end of a given word doesn’t matter
        4. If a subset of words match, it still counts as a match
        5. Capitalization doesn’t matter
    """
    hit_count = 0
    records = SDNFallbackData.get_current_records_and_filter_by_source_and_type(
        'Specially Designated Nationals (SDN) - Treasury Department', 'Individual'
    )
    records = records.filter(countries__contains=country)
    processed_name, processed_city = process_text(name), process_text(city)
    for record in records:
        record_names, record_addresses = set(record.names.split()), set(record.addresses.split())
        if (processed_name.issubset(record_names) and processed_city.issubset(record_addresses)):
            hit_count = hit_count + 1
    return hit_count


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


def process_text(text):
    """
    Lowercase, remove non-alphanumeric characters, and ignore order and word frequency.
    Attempts to transliterate unicode characters into ascii (such as accented characters into
    non-accented characters).

    Args:
        text (str): names or addresses from the sdn list to be processed

    Returns:
        text (set): processed text
    """
    if len(text) == 0:
        return ''

    # transliterate unicode characters into ascii
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    text = text.lower()

    # Strip non-alphanumeric characters from each word
    # Ignore order and word frequency
    text = set(filter(None, set(re.split('[^a-zA-Z0-9]', text))))

    return text


def extract_country_information(addresses, ids):
    """ Extract any country codes that are present, if any, in the addresses and ids fields

    Args:
        addresses (str): addresses from the csv addresses field
        ids (str): ids from the csv ids field

    Returns:
        countries (str): Space separated list of alpha_2 country codes present in the addresses and ids fields
    """
    country_matches = []
    if addresses:
        # Addresses are stored in a '; ' separated format with the country at the end of each address
        # We check for two uppercase letters followed by '; ' or at the end of the string
        addresses_regex = r'([A-Z]{2})$|([A-Z]{2});'
        country_matches += re.findall(addresses_regex, addresses)
    if ids:
        # Ids are stored in a '; ' separated format with the country at the beginning of each id
        # Countries within the id are followed by a comma
        # We check for two uppercase letters prefaced by '; ' or at the beginning of a string
        # Notes are also stored in this field in sentence case, so checking for two uppercase letters handles this
        ids_regex = r'^([A-Z]{2}),|; ([A-Z]{2}),'
        country_matches += re.findall(ids_regex, ids)
    # country_matches is returned in the following format [('', 'IQ'), ('', 'JO'), ('', 'IQ'), ('', 'TR')]
    # We filter out regex groups with no match, deduplicate countries, and convert them to a space separated string
    # with the following format 'IQ JO TR'
    country_codes = {' '.join(tuple(filter(None, x))) for x in country_matches}
    valid_country_codes = COUNTRY_CODES.intersection(country_codes)
    formatted_countries = ' '.join(valid_country_codes)
    return formatted_countries


def populate_sdn_fallback_metadata(sdn_csv_string):
    """
    Insert a new SDNFallbackMetadata entry if the new csv differs from the current one

    Args:
        sdn_csv_string (bytes): Bytes of the sdn csv

    Returns:
        sdn_fallback_metadata_entry (SDNFallbackMetadata): Instance of the current SDNFallbackMetadata class
        or None if none exists
    """
    file_checksum = hashlib.sha256(sdn_csv_string.encode('utf-8')).hexdigest()
    metadata_entry = SDNFallbackMetadata.insert_new_sdn_fallback_metadata_entry(file_checksum)
    return metadata_entry


def populate_sdn_fallback_data(sdn_csv_string, metadata_entry):
    """
    Process CSV data and create SDNFallbackData records

    Args:
        sdn_csv_string (str): String of the sdn csv
        metadata_entry (SDNFallbackMetadata): Instance of the current SDNFallbackMetadata class
    """
    sdn_csv_reader = csv.DictReader(io.StringIO(sdn_csv_string))
    processed_records = []
    for row in sdn_csv_reader:
        sdn_source, sdn_type, names, addresses, alt_names, ids = (
            row['source'] or '', row['type'] or '', row['name'] or '',
            row['addresses'] or '', row['alt_names'] or '', row['ids'] or ''
        )
        processed_names = ' '.join(process_text(' '.join(filter(None, [names, alt_names]))))
        processed_addresses = ' '.join(process_text(addresses))
        countries = extract_country_information(addresses, ids)
        processed_records.append(SDNFallbackData(
            sdn_fallback_metadata=metadata_entry,
            source=sdn_source,
            sdn_type=sdn_type,
            names=processed_names,
            addresses=processed_addresses,
            countries=countries
        ))
    # Bulk create should be more efficient for a few thousand records without needing to use SQL directly.
    SDNFallbackData.objects.bulk_create(processed_records)


def populate_sdn_fallback_data_and_metadata(sdn_csv_string):
    """
    1. Create the SDNFallbackMetadata entry
    2. Populate the SDNFallbackData from the csv

    Args:
        sdn_csv_string (str): String of the sdn csv
    """
    metadata_entry = populate_sdn_fallback_metadata(sdn_csv_string)
    if metadata_entry:
        populate_sdn_fallback_data(sdn_csv_string, metadata_entry)
        # Once data is successfully imported, update the metadata import timestamp and state
        now = datetime.now(timezone.utc)
        metadata_entry.import_timestamp = now
        metadata_entry.save()
        metadata_entry.swap_all_states()
    return metadata_entry


def compare_SDNCheck_vs_fallback(basket_id, data, hit_count):
    """ Temporary checkSDNFallback comparison call (REV-1338)

    Args:
        basket ID (int): ID of the current basket
        form data (dictionary): data inputted on checkout form
        hit_count from checkSDN (int): result this basket got during SDN API call

    Returns:
        No return values. Print results comparison, and additional info for problem case (API hit but fallback miss)

    """
    try:
        SDNFallback_hit = checkSDNFallback(
            data.get('first_name') + ' ' + data.get('last_name'),
            data.get('city'),
            data.get('country')
        )

    except (SDNFallbackDataEmptyError, Exception) as e:  # pylint: disable=broad-except
        # We're making this shadow call to gather comparison info for the csv sdn fallback vs SDN API.
        # We don't want to prevent learners from purchasing if there's an error in the csv sdn fallback.
        logger.warning("Skip SDN API vs fallback comparison; exception calling checkSDNFallback")
        logger.exception(e)
    else:
        # If shadow fallback call ran, log comparison of results vs those from the SDN API
        # A match is where both found a hit or neither found a hit
        SDN_calls_matched = (hit_count > 0 and SDNFallback_hit) or (hit_count == 0 and not SDNFallback_hit)
        result_string = "SDNFallback compare: MATCH" if SDN_calls_matched else "SDNFallback compare: MISMATCH"
        logger.info(
            '%s. Results - SDN API: %d hit(s); SDN Fallback: %s hit(s). Basket: %d',
            result_string,
            hit_count,
            SDNFallback_hit,
            basket_id,
        )

        if hit_count > 0 and not SDN_calls_matched:
            logger.info('Failed SDN match for first name: %s, last name: %s, city: %s, country: %s ',
                        data.get('first_name'),
                        data.get('last_name'),
                        data.get('city'),
                        data.get('country'))
