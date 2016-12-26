import hashlib
from urlparse import parse_qs, urlparse

from django.conf import settings
from django.core.cache import cache
from django.utils.translation import ugettext_lazy as _


def mode_for_seat(product):
    """
    Returns the enrollment mode (aka course mode) for the specified product.
    If the specified product does not include a 'certificate_type' attribute it is likely the
    bulk purchase "enrollment code" product variant of the single-seat product, so we attempt
    to locate the 'seat_type' attribute in its place.
    """
    mode = getattr(product.attr, 'certificate_type', getattr(product.attr, 'seat_type', None))
    if not mode:
        return 'audit'
    if mode == 'professional' and not getattr(product.attr, 'id_verification_required', False):
        return 'no-id-professional'
    return mode


def get_course_info_from_catalog(site, course_key):
    """ Get course information from catalog service and cache """
    api = site.siteconfiguration.course_catalog_api_client
    partner_short_code = site.siteconfiguration.partner.short_code
    cache_key = 'courses_api_detail_{}{}'.format(course_key, partner_short_code)
    cache_key = hashlib.md5(cache_key).hexdigest()
    course_run = cache.get(cache_key)
    if not course_run:  # pragma: no cover
        course_run = api.course_runs(course_key).get(partner=partner_short_code)
        cache.set(cache_key, course_run, settings.COURSES_API_CACHE_TIMEOUT)
    return course_run


def get_course_catalogs(site, resource_id=None):
    """
    Get details related to course catalogs from Catalog Service.

    Arguments:
        site (Site): Site object containing Site Configuration data
        resource_id (int or str): Identifies a specific resource to be retrieved

    Returns:
        dict: Course catalogs received from Course Catalog API

    """
    resource = 'catalogs'
    base_cache_key = '{}.catalog.api.data'.format(site.domain)

    cache_key = '{}.{}'.format(base_cache_key, resource_id) if resource_id else base_cache_key
    cache_key = hashlib.md5(cache_key).hexdigest()
    cached = cache.get(cache_key)
    if cached:
        return cached

    api = site.siteconfiguration.course_catalog_api_client
    endpoint = getattr(api, resource)
    response = endpoint(resource_id).get()

    if resource_id:
        results = response
    else:
        results = traverse_pagination(response, endpoint)

    cache.set(cache_key, results, settings.COURSES_API_CACHE_TIMEOUT)
    return results


def traverse_pagination(response, endpoint):
    """
    Traverse a paginated API response.

    Extracts and concatenates "results" (list of dict) returned by DRF-powered
    APIs.

    Arguments:
        response (Dict): Current response dict from service API
        endpoint (slumber Resource object): slumber Resource object from edx-rest-api-client

    Returns:
        list of dict.

    """
    results = response.get('results', [])

    next_page = response.get('next')
    while next_page:
        querystring = parse_qs(urlparse(next_page).query, keep_blank_values=True)
        response = endpoint.get(**querystring)
        results += response.get('results', [])
        next_page = response.get('next')

    return results


def get_certificate_type_display_value(certificate_type):
    display_values = {
        'audit': _('Audit'),
        'credit': _('Credit'),
        'honor': _('Honor'),
        'professional': _('Professional'),
        'verified': _('Verified'),
    }

    if certificate_type not in display_values:
        raise ValueError('Certificate Type [%s] not found.', certificate_type)

    return display_values[certificate_type]
