
from urllib.parse import urljoin

from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from edx_django_utils.cache import TieredCache
from opaque_keys.edx.keys import CourseKey

from ecommerce.core.utils import deprecated_traverse_pagination, get_cache_key


def mode_for_product(product):
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


def _get_discovery_response(site, cache_key, resource, resource_id):
    """
    Return the discovery endpoint result of given resource or cached response if its already been cached.

    Arguments:
        site (Site): Site object containing Site Configuration data
        cache_key (str): Cache key for given resource
        resource_id (int or str): Identifies a specific resource to be retrieved

    Returns:
        dict: resource's information for given resource_id received from Discovery API
    """
    course_cached_response = TieredCache.get_cached_response(cache_key)
    if course_cached_response.is_found:
        return course_cached_response.value

    params = {}

    if resource == 'course_runs':
        params['partner'] = site.siteconfiguration.partner.short_code

    api_client = site.siteconfiguration.oauth_api_client
    resource_path = f"{resource_id}/" if resource_id else ""
    discovery_api_url = urljoin(
        f"{site.siteconfiguration.discovery_api_url}/",
        f"{resource}/{resource_path}"
    )

    response = api_client.get(discovery_api_url, params=params)
    response.raise_for_status()

    result = response.json()

    if resource_id is None:
        result = deprecated_traverse_pagination(result, api_client, discovery_api_url)

    TieredCache.set_all_tiers(cache_key, result, settings.COURSES_API_CACHE_TIMEOUT)
    return result


def get_course_detail(site, course_resource_id):
    """
    Return the course information of given course's resource from Discovery Service and cache.

    Arguments:
        site (Site): Site object containing Site Configuration data
        course_resource_id (UUID or str): It can be course UUID or course key

    Returns:
        dict: Course information received from Discovery API
    """
    resource = "courses"
    cache_key = get_cache_key(
        site_domain=site.domain,
        resource="{}-{}".format(resource, course_resource_id)
    )
    return _get_discovery_response(site, cache_key, resource, course_resource_id)


def get_course_run_detail(site, course_run_key):
    """
    Return the course run information of given course_run_key from Discovery Service and cache.

    Arguments:
        site (Site): Site object containing Site Configuration data
        course_run_key (str): Course run key

    Returns:
        dict: CourseRun information received from Discovery API
    """
    resource = "course_runs"
    cache_key = get_cache_key(
        site_domain=site.domain,
        resource="{}-{}".format(resource, course_run_key)
    )
    return _get_discovery_response(site, cache_key, resource, course_run_key)


def get_course_info_from_catalog(site, product):
    """ Get course or course_run information from Discovery Service and cache """
    if product.is_course_entitlement_product:
        response = get_course_detail(site, product.attr.UUID)
    else:
        response = get_course_run_detail(site, CourseKey.from_string(product.attr.course_key))
    return response


def get_course_catalogs(site, resource_id=None):
    """
    Get details related to course catalogs from Discovery Service.

    Arguments:
        site (Site): Site object containing Site Configuration data
        resource_id (int or str): Identifies a specific resource to be retrieved

    Returns:
        dict: Course catalogs received from Discovery API

    Raises:
        HTTPError: requests exception "HTTPError"
    """
    resource = "catalogs"
    cache_key = get_cache_key(
        site_domain=site.domain,
        resource=resource if resource_id is None else "{}-{}".format(resource, resource_id)
    )
    return _get_discovery_response(site, cache_key, 'catalogs', resource_id)


def get_certificate_type_display_value(certificate_type):
    display_values = {
        'audit': _('Audit'),
        'credit': _('Credit'),
        'honor': _('Honor'),
        'professional': _('Professional'),
        'verified': _('Verified'),
        'executive-education': _('Executive Education'),
        'paid-executive-education': _('Paid Executive Education'),
        'unpaid-executive-education': _('Unpaid Executive Education'),
        'paid-bootcamp': _('Paid Bootcamp'),
        'unpaid-bootcamp': _('Unpaid Bootcamp'),
    }

    if certificate_type not in display_values:
        raise ValueError('Certificate Type [{}] not found.'.format(certificate_type))

    return display_values[certificate_type]
