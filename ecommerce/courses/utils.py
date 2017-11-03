import hashlib

from django.conf import settings
from django.core.cache import cache
from django.utils.translation import ugettext_lazy as _
from opaque_keys.edx.keys import CourseKey

from ecommerce.core.utils import traverse_pagination


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


def get_course_info_from_catalog(site, product):
    """ Get course or course_run information from Discovery Service and cache """
    if product.is_course_entitlement_product:
        key = product.attr.UUID
    else:
        key = CourseKey.from_string(product.attr.course_key)

    api = site.siteconfiguration.discovery_api_client
    partner_short_code = site.siteconfiguration.partner.short_code
    cache_key = 'courses_api_detail_{}{}'.format(key, partner_short_code)
    cache_key = hashlib.md5(cache_key).hexdigest()
    course = cache.get(cache_key)
    if not course:  # pragma: no cover
        if product.is_course_entitlement_product:
            course = api.courses(key).get()
        else:
            course = api.course_runs(key).get(partner=partner_short_code)
        cache.set(cache_key, course, settings.COURSES_API_CACHE_TIMEOUT)
    return course


def get_course_catalogs(site, resource_id=None):
    """
    Get details related to course catalogs from Discovery Service.

    Arguments:
        site (Site): Site object containing Site Configuration data
        resource_id (int or str): Identifies a specific resource to be retrieved

    Returns:
        dict: Course catalogs received from Discovery API

    Raises:
        ConnectionError: requests exception "ConnectionError"
        SlumberBaseException: slumber exception "SlumberBaseException"
        Timeout: requests exception "Timeout"

    """
    resource = 'catalogs'
    base_cache_key = '{}.catalog.api.data'.format(site.domain)

    cache_key = '{}.{}'.format(base_cache_key, resource_id) if resource_id else base_cache_key
    cache_key = hashlib.md5(cache_key).hexdigest()
    cached = cache.get(cache_key)
    if cached:
        return cached

    api = site.siteconfiguration.discovery_api_client
    endpoint = getattr(api, resource)
    response = endpoint(resource_id).get()

    if resource_id:
        results = response
    else:
        results = traverse_pagination(response, endpoint)

    cache.set(cache_key, results, settings.COURSES_API_CACHE_TIMEOUT)
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
