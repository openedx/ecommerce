""" Coupon related utility functions. """
import hashlib

from django.conf import settings
from django.core.cache import cache
from oscar.core.loading import get_model

from ecommerce.core.constants import DEFAULT_CATALOG_PAGE_SIZE

Product = get_model('catalogue', 'Product')


def get_range_catalog_query_results(limit, query, site, offset=None):
    """
    Get catalog query results

    Arguments:
        limit (int): Number of results per page
        query (str): ElasticSearch Query
        site (Site): Site object containing Site Configuration data
        offset (int): Page offset

    Returns:
        dict: Query seach results received from Course Catalog API
    """
    cache_key = 'course_runs_{}_{}_{}'.format(query, limit, offset)
    cache_hash = hashlib.md5(cache_key).hexdigest()
    response = cache.get(cache_hash)
    if not response:
        response = site.siteconfiguration.course_catalog_api_client.course_runs.get(
            limit=limit,
            offset=offset,
            q=query,
        )
        cache.set(cache_hash, response, settings.COURSES_API_CACHE_TIMEOUT)
    return response


def get_seats_from_query(site, query, seat_types):
    """
    Retrieve seats from a course catalog query and matching seat types.

    Arguments:
        site (Site): current site
        query (str): course catalog query
        seat_types (str): a string with comma-separated accepted seat type names

    Returns:
        List of seat products retrieved from the course catalog query.
    """
    results = get_range_catalog_query_results(
        limit=DEFAULT_CATALOG_PAGE_SIZE,
        query=query,
        site=site
    )['results']
    query_products = []
    for course in results:
        try:
            product = Product.objects.get(
                course_id=course['key'],
                attributes__name='certificate_type',
                attribute_values__value_text__in=seat_types.split(',')
            )
            query_products.append(product)
        except Product.DoesNotExist:
            pass
    return query_products


def prepare_course_seat_types(course_seat_types):
    """
    Convert list of course seat types into comma-separated string.

    Arguments:
        course_seat_types (list): List of course seat types

    Returns:
        str: Comma-separated list of course seat types if course_seat_types is not empty
    """
    return ','.join(seat_type.lower() for seat_type in course_seat_types)
