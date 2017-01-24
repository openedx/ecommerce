""" Coupon related utility functions. """
import hashlib

from django.conf import settings
from django.core.cache import cache
from oscar.core.loading import get_model

from ecommerce.courses.utils import traverse_pagination


Product = get_model('catalogue', 'Product')


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
    cache_key = '{site_domain}_{partner_code}_{resource}_{query}_{limit}_{offset}'.format(
        site_domain=site.domain,
        partner_code=partner_code,
        resource=api_resource_name,
        query=query,
        limit=limit,
        offset=offset
    )
    cache_key = hashlib.md5(cache_key).hexdigest()

    response = cache.get(cache_key)
    if not response:
        api = site.siteconfiguration.course_catalog_api_client
        endpoint = getattr(api, api_resource_name)

        if limit:
            response = endpoint().get(
                partner=partner_code,
                q=query,
                limit=limit,
                offset=offset
            )
        else:
            response = endpoint().get(
                partner=partner_code,
                q=query
            )
            all_response_results = traverse_pagination(response, endpoint)
            response = {
                'count': len(all_response_results),
                'next': 'None',
                'previous': 'None',
                'results': all_response_results,
            }

        cache.set(cache_key, response, settings.COURSES_API_CACHE_TIMEOUT)

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
