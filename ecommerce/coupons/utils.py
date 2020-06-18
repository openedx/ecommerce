""" Coupon related utility functions. """


import hashlib
import logging

from django.conf import settings
from django.utils import timezone
from edx_django_utils.cache import TieredCache
from oscar.core.loading import get_model
from slumber.exceptions import HttpNotFoundError

from ecommerce.core.utils import get_cache_key

Product = get_model('catalogue', 'Product')

logger = logging.getLogger(__name__)


def get_catalog_course_runs(site, query, limit=None, offset=None):
    """
    Get course runs for a site on the basis of provided query from the Course
    Catalog API.

    This method will get all course runs by recursively retrieving API
    next urls in the API response if no limit is provided.

    Arguments:
        limit (int): Number of results per page
        offset (int): Page offset
        query (str): ElasticSearch Query
        site (Site): Site object containing Site Configuration data

    Example:
        >>> get_catalog_course_runs(site, query, limit=1)
        {
            "count": 1,
            "next": "None",
            "previous": "None",
            "results": [{
                "key": "course-v1:edX+DemoX+Demo_Course",
                "title": edX Demonstration Course,
                "start": "2016-05-01T00:00:00Z",
                "image": {
                    "src": "path/to/the/course/image"
                },
                "enrollment_end": None
            }],
        }
    Returns:
        dict: Query search results for course runs received from Course
            Catalog API

    Raises:
        ConnectionError: requests exception "ConnectionError"
        SlumberBaseException: slumber exception "SlumberBaseException"
        Timeout: requests exception "Timeout"

    """
    api_resource_name = 'course_runs'
    partner_code = site.siteconfiguration.partner.short_code
    cache_key = u'{site_domain}_{partner_code}_{resource}_{query}_{limit}_{offset}'.format(
        site_domain=site.domain,
        partner_code=partner_code,
        resource=api_resource_name,
        query=query,
        limit=limit,
        offset=offset
    )
    cache_key = hashlib.md5(cache_key.encode('utf-8')).hexdigest()

    cached_response = TieredCache.get_cached_response(cache_key)
    if cached_response.is_found:
        return cached_response.value

    api = site.siteconfiguration.discovery_api_client
    endpoint = getattr(api, api_resource_name)

    response = endpoint().get(
        partner=partner_code,
        q=query,
        limit=limit,
        offset=offset
    )
    TieredCache.set_all_tiers(cache_key, response, settings.COURSES_API_CACHE_TIMEOUT)
    return response


def prepare_course_seat_types(course_seat_types):
    """
    Convert list of course seat types into comma-separated string.

    Arguments:
        course_seat_types (list): List of course seat types

    Returns:
        str: Comma-separated list of course seat types if course_seat_types is not empty
    """
    if course_seat_types:
        return ','.join(seat_type.lower() for seat_type in course_seat_types)
    return None


def fetch_course_catalog(site, catalog_id):
    """
    Fetch course catalog for the given catalog id.

    This method will fetch catalog for given catalog id, if there is no catalog with the given
    catalog id, method will return `None`.

    Arguments:
        site (Site): Instance of the current site.
        catalog_id (int): An integer specifying the primary key value of catalog to fetch.

    Example:
        >>> fetch_course_catalog(site, catalog_id=1)
        {
            "id": 1,
            "name": "All Courses",
            "query": "*:*",
            ...
        }
    Returns:
        (dict): A dictionary containing key/value pairs corresponding to catalog attribute/values.

    Raises:
        ConnectionError: requests exception "ConnectionError", raised if if ecommerce is unable to connect
            to enterprise api server.
        SlumberBaseException: base slumber exception "SlumberBaseException", raised if API response contains
            http error status like 4xx, 5xx etc.
        Timeout: requests exception "Timeout", raised if enterprise API is taking too long for returning
            a response. This exception is raised for both connection timeout and read timeout.

    """
    api_resource = 'catalogs'

    cache_key = get_cache_key(
        site_domain=site.domain,
        resource=api_resource,
        catalog_id=catalog_id,
    )

    cached_response = TieredCache.get_cached_response(cache_key)
    if cached_response.is_found:
        return cached_response.value

    api = site.siteconfiguration.discovery_api_client
    endpoint = getattr(api, api_resource)

    try:
        response = endpoint(catalog_id).get()
    except HttpNotFoundError:
        logger.exception("Catalog '%s' not found.", catalog_id)
        raise

    TieredCache.set_all_tiers(cache_key, response, settings.COURSES_API_CACHE_TIMEOUT)
    return response


def is_voucher_applied(basket, voucher):
    """
    Check if given voucher is applied to the given basket.

    Arguments:
        basket (Basket): oscar basket object to checked for discount voucher.
        voucher (Voucher): Discount voucher.

    Returns:
         (bool): True if given voucher is applied to the basket, False otherwise
    """
    # Look for discounts from this new voucher
    for discount in basket.offer_applications:
        if discount['voucher'] and discount['voucher'] == voucher:
            return True
    return False


def is_coupon_available(coupon):
    """
    Returns True if `coupon` is available, False otherwise.
    """
    voucher = coupon.attr.coupon_vouchers.vouchers.first()
    start_datetime = voucher.start_datetime
    end_datetime = voucher.end_datetime
    current_datetime = timezone.now()
    return start_datetime < current_datetime < end_datetime
