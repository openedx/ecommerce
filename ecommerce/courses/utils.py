import hashlib

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
    cache_hash = hashlib.md5(cache_key).hexdigest()
    course_run = cache.get(cache_hash)
    if not course_run:  # pragma: no cover
        course_run = api.course_runs(course_key).get(partner=partner_short_code)
        cache.set(cache_hash, course_run, settings.COURSES_API_CACHE_TIMEOUT)
    return course_run


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
