import hashlib

from django.conf import settings
from django.core.cache import cache


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


def get_course_info(site, course_key):
    """ Get course information from Course Catalog via the course api and cache """
    api = site.siteconfiguration.course_catalog_api_client
    cache_key = 'courses_api_detail_{}'.format(course_key)
    cache_hash = hashlib.md5(cache_key).hexdigest()
    course = cache.get(cache_hash)
    if not course:  # pragma: no cover
        response = api.course_runs.get(q='key:"{}"'.format(course_key))
        try:
            course = response['results'][0]
            cache.set(cache_hash, course, settings.COURSES_API_CACHE_TIMEOUT)
        except (AttributeError, IndexError):
            pass
    return course
