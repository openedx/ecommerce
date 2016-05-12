from urlparse import urljoin

from django.conf import settings
from edx_rest_api_client.client import EdxRestApiClient
from threadlocals.threadlocals import get_current_request

from ecommerce.core.exceptions import MissingRequestError


def get_ecommerce_url(path=''):
    """
    Returns path joined with the appropriate ecommerce URL root for the current site

    Raises:
        MissingRequestError: If the current ecommerce site is not in threadlocal storage
    """
    request = get_current_request()
    if request:
        ecommerce_url_root = "{}://{}".format(request.scheme, request.site.domain)
        return urljoin(ecommerce_url_root, path)
    raise MissingRequestError


def get_lms_commerce_api_url():
    return get_lms_url('/api/commerce/v1/')


def get_lms_dashboard_url():
    return get_lms_url('/dashboard')


def get_lms_enrollment_api_url():
    return get_lms_url('/api/enrollment/v1/enrollment')


def get_lms_enrollment_base_api_url():
    """ Returns the Base lms enrollment api url."""
    return get_lms_url('/api/enrollment/v1')


def get_lms_heartbeat_url():
    return get_lms_url('/heartbeat')


def get_lms_url(path=''):
    """
    Returns path joined with the appropriate LMS URL root for the current site

    Raises:
        MissingRequestError: If the current ecommerce site is not in threadlocal storage
    """
    request = get_current_request()
    if request:
        return urljoin(request.site.siteconfiguration.lms_url_root, path)
    raise MissingRequestError


def get_oauth2_provider_url():
    return get_lms_url('/oauth2')


def get_course_catalog_api_client(site):
    """
    Returns an API client to access the Course Catalog service.

    Arguments:
        site (Site): The site for which to retrieve settings.

    Returns:
        EdxRestApiClient: The client to access the Course Catalog service.
    """

    access_token, __ = EdxRestApiClient.get_oauth_access_token(
        '{root}/access_token'.format(root=get_oauth2_provider_url()),
        site.siteconfiguration.oauth_settings['SOCIAL_AUTH_EDX_OIDC_KEY'],
        site.siteconfiguration.oauth_settings['SOCIAL_AUTH_EDX_OIDC_SECRET'],
        token_type='jwt'
    )
    course_catalog_client = EdxRestApiClient(
        settings.COURSE_CATALOG_API_URL,
        jwt=access_token
    )
    return course_catalog_client
