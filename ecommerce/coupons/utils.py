""" Coupon related utility functions. """
from oscar.core.loading import get_model

from ecommerce.core.constants import DEFAULT_CATALOG_PAGE_SIZE

Product = get_model('catalogue', 'Product')


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
    response = site.siteconfiguration.course_catalog_api_client.course_runs.get(q=query,
                                                                                page_size=DEFAULT_CATALOG_PAGE_SIZE,
                                                                                limit=DEFAULT_CATALOG_PAGE_SIZE)
    query_products = []
    for result in response['results']:
        try:
            product = Product.objects.get(
                course_id=result['key'],
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
