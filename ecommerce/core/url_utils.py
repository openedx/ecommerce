

import warnings

from django.http import HttpResponseRedirect
from django.urls import reverse
from threadlocals.threadlocals import get_current_request

from ecommerce.core.exceptions import MissingRequestError


def _get_site_configuration():
    """ Retrieve the SiteConfiguration from the current request from the global thread.

    Notes:
        This is a stopgap. Do NOT use this with any expectation that it will remain in place.
        This function WILL be removed.
    """
    warnings.warn('Usage of _get_site_configuration and django-threadlocals is deprecated. '
                  'Use the helper methods on the SiteConfiguration model.', DeprecationWarning)

    request = get_current_request()

    if request:
        return request.site.siteconfiguration

    raise MissingRequestError


def get_ecommerce_url(path=''):
    """
    Returns path joined with the appropriate ecommerce URL root for the current site

    Raises:
        MissingRequestError: If the current ecommerce site is not in threadlocal storage
    """
    site_configuration = _get_site_configuration()
    return site_configuration.build_ecommerce_url(path)


def get_lms_courseware_url(course_run_id):
    """
    Return the courseware URL for the given course run.

    Arguments:
        course_run_id (string): The serialized course run ID.

    Returns:
        string: The courseware URL.
    """
    return get_lms_url('courses/{}/info'.format(course_run_id))


def get_lms_course_about_url(course_key):
    """
    Return the courseware about URL for the given course key.

    Returns:
        string: The course about page URL.
    """
    return get_lms_url('courses/{}/about'.format(course_key))


def get_lms_explore_courses_url():
    """
    Return the explore courses url.
    """
    return get_lms_url('courses')


def get_lms_dashboard_url():
    site_configuration = _get_site_configuration()
    return site_configuration.student_dashboard_url


def get_lms_program_dashboard_url(uuid):
    site_configuration = _get_site_configuration()
    return site_configuration.build_program_dashboard_url(uuid)


def get_lms_enrollment_api_url():
    # TODO Update consumers of this method to use `get_lms_enrollment_base_api_url` (which should be renamed
    # get_lms_enrollment_api_url).
    return get_lms_url('/api/enrollment/v1/enrollment')


def get_lms_entitlement_api_url():
    """ Returns the base lms entitlement api url. """
    return get_lms_url('/api/entitlements/v1/')


def get_lms_enrollment_base_api_url():
    """ Returns the Base lms enrollment api url."""
    site_configuration = _get_site_configuration()
    return site_configuration.enrollment_api_url


def get_lms_url(path=''):
    """
    Returns path joined with the appropriate LMS URL root for the current site

    Raises:
        MissingRequestError: If the current ecommerce site is not in threadlocal storage
    """
    site_configuration = _get_site_configuration()
    return site_configuration.build_lms_url(path)


def get_oauth2_provider_url():
    site_configuration = _get_site_configuration()
    return site_configuration.oauth2_provider_url


def absolute_url(request, reverse_string):
    return request.build_absolute_uri(reverse(reverse_string))


def absolute_redirect(request, reverse_string):
    return HttpResponseRedirect(absolute_url(request, reverse_string))
