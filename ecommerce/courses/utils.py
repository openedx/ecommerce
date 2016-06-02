import hashlib

from django.conf import settings
from django.core.cache import cache
from edx_rest_api_client.client import EdxRestApiClient

from ecommerce.core.url_utils import get_lms_url


def mode_for_seat(seat):
    """ Returns the Enrollment mode for a given seat product. """
    certificate_type = getattr(seat.attr, 'certificate_type', '')

    if certificate_type == 'professional' and not seat.attr.id_verification_required:
        return 'no-id-professional'
    elif certificate_type == '':
        return 'audit'

    return certificate_type


def get_course_info_from_lms(course_key):
    """ Get course information from LMS via the course api and cache """
    api = EdxRestApiClient(get_lms_url('api/courses/v1/'))
    cache_key = 'courses_api_detail_{}'.format(course_key)
    cache_hash = hashlib.md5(cache_key).hexdigest()
    course = cache.get(cache_hash)
    if not course:  # pragma: no cover
        course = api.courses(course_key).get()
        cache.set(cache_hash, course, settings.COURSES_API_CACHE_TIMEOUT)
    return course
