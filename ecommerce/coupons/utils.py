""" Coupon related utility functions. """
import hashlib
import logging

from django.conf import settings
from django.core.cache import cache
from oscar.core.loading import get_model


log = logging.getLogger(__name__)
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
    partner_code = site.siteconfiguration.partner.short_code
    cache_key = 'course_runs_{}_{}_{}_{}'.format(query, limit, offset, partner_code)
    cache_key = hashlib.md5(cache_key).hexdigest()
    response = cache.get(cache_key)
    if not response:
        response = site.siteconfiguration.course_catalog_api_client.course_runs.get(
            limit=limit,
            offset=offset,
            q=query,
            partner=partner_code
        )
        cache.set(cache_key, response, settings.COURSES_API_CACHE_TIMEOUT)
    return response


def get_all_course_catalogs(site):
    """
    Get all course catalogs.

    Arguments:
        site (Site): Site object containing Site Configuration data

    Returns:
        dict: Course catalogs received from Course Catalog API
    """
    no_data = []
    resource = 'catalogs'
    api = site.siteconfiguration.course_catalog_api_client
    try:
        endpoint = getattr(api, resource)
        resource_id = None
        querystring = {}
        response = endpoint(resource_id).get(**querystring)

        if resource_id:
            results = response
        else:
            results = _traverse_pagination(response, endpoint, querystring, no_data)
    except:  # pylint: disable=bare-except
        log.exception('Failed to retrieve data from the Discovery API.')
        return no_data

    return results


def _traverse_pagination(response, endpoint, querystring, no_data):
    """Traverse a paginated API response.

    Extracts and concatenates "results" (list of dict) returned by DRF-powered APIs.
    """
    results = response.get('results', no_data)

    page = 1
    next_page = response.get('next')
    while next_page:
        page += 1
        querystring['page'] = page
        response = endpoint.get(**querystring)
        results += response.get('results', no_data)
        next_page = response.get('next')

    return results


def prepare_course_seat_types(course_seat_types):
    """
    Convert list of course seat types into comma-separated string.

    Arguments:
        course_seat_types (list): List of course seat types

    Returns:
        str: Comma-separated list of course seat types if course_seat_types is not empty
    """
    return ','.join(seat_type.lower() for seat_type in course_seat_types)
