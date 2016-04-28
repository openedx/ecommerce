from datetime import timedelta
import logging

from edx_rest_api_client.client import EdxRestApiClient
from dateutil.parser import parse
from slumber.exceptions import SlumberBaseException
from requests.exceptions import ConnectionError, Timeout

from ecommerce.core.url_utils import get_lms_url

logger = logging.getLogger(__name__)


def mode_for_seat(seat):
    """ Returns the Enrollment mode for a given seat product. """
    certificate_type = getattr(seat.attr, 'certificate_type', '')

    if certificate_type == 'professional' and not seat.attr.id_verification_required:
        return 'no-id-professional'
    elif certificate_type == '':
        return 'audit'

    return certificate_type


def get_default_seat_upgrade_deadline(course_id, days_in_past=10):
    """
    Returns default upgrade deadline which is 10 days before the course end datetime and returns None
    in case of exception.
    """
    api = EdxRestApiClient(get_lms_url('api/courses/v1/'))
    try:
        course_info = api.courses(course_id).get()
        course_end = course_info['end']
        return parse(course_end) - timedelta(days=days_in_past) if course_end else None
    except (ConnectionError, SlumberBaseException, Timeout):
        logger.exception('Failed to retrieve data from Course API for course [%s].', course_id)
        return None
