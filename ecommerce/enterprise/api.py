"""
Methods for fetching enterprise API data.
"""
import logging
from urllib import urlencode

from django.conf import settings
from edx_django_utils.cache import TieredCache
from edx_rest_api_client.client import EdxRestApiClient
from requests.exceptions import ConnectionError, Timeout
from slumber.exceptions import SlumberHttpBaseException

from ecommerce.core.utils import get_cache_key

logger = logging.getLogger(__name__)


def fetch_enterprise_learner_entitlements(site, learner_id):
    """
    Fetch enterprise learner entitlements along-with data sharing consent requirement.

    Arguments:
        site (Site): site instance.
        learner_id (int): Primary key identifier for the enterprise learner.

    Example:
        >>> from django.contrib.sites.shortcuts import get_current_site
        >>> site  = get_current_site()
        >>> fetch_enterprise_learner_entitlements(site, 1)
        [
            {
                "requires_consent": False,
                "entitlement_id": 1
            },
        ]

    Returns:
         (list): Containing dicts of the following structure
            {
                "requires_consent": True,
                "entitlement_id": 1
            }

    Raises:
        ConnectionError: requests exception "ConnectionError", raised if if ecommerce is unable to connect
            to enterprise api server.
        SlumberBaseException: base slumber exception "SlumberBaseException", raised if API response contains
            http error status like 4xx, 5xx etc.
        Timeout: requests exception "Timeout", raised if enterprise API is taking too long for returning
            a response. This exception is raised for both connection timeout and read timeout.
    """
    resource_url = 'enterprise-learner/{learner_id}/entitlements'.format(learner_id=learner_id)
    cache_key = get_cache_key(
        site_domain=site.domain,
        partner_code=site.siteconfiguration.partner.short_code,
        resource=resource_url,
        learner_id=learner_id
    )

    entitlements_cached_response = TieredCache.get_cached_response(cache_key)
    if entitlements_cached_response.is_found:
        return entitlements_cached_response.value

    api = site.siteconfiguration.enterprise_api_client
    entitlements = getattr(api, resource_url).get()

    TieredCache.set_all_tiers(cache_key, entitlements, settings.ENTERPRISE_API_CACHE_TIMEOUT)
    return entitlements


def fetch_enterprise_learner_data(site, user):
    """
    Fetch information related to enterprise and its entitlements from the Enterprise
    Service.

    Example:
        fetch_enterprise_learner_data(site, user)

    Arguments:
        site: (Site) site instance
        user: (User) django auth user

    Returns:
        dict: {
            "enterprise_api_response_for_learner": {
                "count": 1,
                "num_pages": 1,
                "current_page": 1,
                "results": [
                    {
                        "enterprise_customer": {
                            "uuid": "cf246b88-d5f6-4908-a522-fc307e0b0c59",
                            "name": "BigEnterprise",
                            "catalog": 2,
                            "active": true,
                            "site": {
                                "domain": "example.com",
                                "name": "example.com"
                            },
                            "enable_data_sharing_consent": true,
                            "enforce_data_sharing_consent": "at_login",
                            "branding_configuration": {
                                "enterprise_customer": "cf246b88-d5f6-4908-a522-fc307e0b0c59",
                                "logo": "https://open.edx.org/sites/all/themes/edx_open/logo.png"
                            },
                            "enterprise_customer_entitlements": [
                                {
                                    "enterprise_customer": "cf246b88-d5f6-4908-a522-fc307e0b0c59",
                                    "entitlement_id": 69
                                }
                            ]
                        },
                        "user_id": 5,
                        "user": {
                            "username": "staff",
                            "first_name": "",
                            "last_name": "",
                            "email": "staff@example.com",
                            "is_staff": true,
                            "is_active": true,
                            "date_joined": "2016-09-01T19:18:26.026495Z"
                        },
                        "data_sharing_consent_records": [
                            {
                                "username": "staff",
                                "enterprise_customer_uuid": "cf246b88-d5f6-4908-a522-fc307e0b0c59",
                                "exists": true,
                                "consent_provided": true,
                                "consent_required": false,
                                "course_id": "course-v1:edX DemoX Demo_Course",
                            }
                        ]
                    }
                ],
                "next": null,
                "start": 0,
                "previous": null
            }
        }

    Raises:
        ConnectionError: requests exception "ConnectionError", raised if if ecommerce is unable to connect
            to enterprise api server.
        SlumberBaseException: base slumber exception "SlumberBaseException", raised if API response contains
            http error status like 4xx, 5xx etc.
        Timeout: requests exception "Timeout", raised if enterprise API is taking too long for returning
            a response. This exception is raised for both connection timeout and read timeout.

    """
    api_resource_name = 'enterprise-learner'
    partner_code = site.siteconfiguration.partner.short_code
    cache_key = get_cache_key(
        site_domain=site.domain,
        partner_code=partner_code,
        resource=api_resource_name,
        username=user.username
    )

    cached_response = TieredCache.get_cached_response(cache_key)
    if cached_response.is_found:
        return cached_response.value

    api = site.siteconfiguration.enterprise_api_client
    endpoint = getattr(api, api_resource_name)
    querystring = {'username': user.username}
    response = endpoint().get(**querystring)

    TieredCache.set_all_tiers(cache_key, response, settings.ENTERPRISE_API_CACHE_TIMEOUT)
    return response


def catalog_contains_course_runs(site, course_run_ids, enterprise_customer_uuid, enterprise_customer_catalog_uuid=None):
    """
    Determine if course runs are associated with the EnterpriseCustomer.
    """
    query_params = {'course_run_ids': course_run_ids}
    api_resource_name = 'enterprise-customer'
    api_resource_id = enterprise_customer_uuid
    if enterprise_customer_catalog_uuid:
        api_resource_name = 'enterprise_catalogs'
        api_resource_id = enterprise_customer_catalog_uuid

    cache_key = get_cache_key(
        site_domain=site.domain,
        resource='{resource}-{resource_id}-contains_content_items'.format(
            resource=api_resource_name,
            resource_id=api_resource_id,
        ),
        query_params=urlencode(query_params, True)
    )

    contains_content_cached_response = TieredCache.get_cached_response(cache_key)
    if contains_content_cached_response.is_found:
        return contains_content_cached_response.value

    api = site.siteconfiguration.enterprise_api_client
    endpoint = getattr(api, api_resource_name)(api_resource_id)
    try:
        contains_content = endpoint.contains_content_items.get(**query_params)['contains_content_items']

        TieredCache.set_all_tiers(cache_key, contains_content, settings.ENTERPRISE_API_CACHE_TIMEOUT)
    except (ConnectionError, KeyError, SlumberHttpBaseException, Timeout):
        logger.exception(
            'Failed to check if course_runs [%s] exist in '
            'EnterpriseCustomerCatalog [%s]'
            'for EnterpriseCustomer [%s].',
            course_run_ids,
            enterprise_customer_catalog_uuid,
            enterprise_customer_uuid,
        )
        contains_content = False
    return contains_content


def get_with_access_to(site, user, enterprise_id):
    """
    Get the enterprises that this user has access to for the data api permission django group.
    """
    api_resource_name = 'enterprise-customer'

    cache_key = get_cache_key(
        resource='{api_resource_name}-with_access_to_enterprises'.format(api_resource_name=api_resource_name),
        user=user.username,
        enterprise_customer=enterprise_id,
    )
    cached_response = TieredCache.get_cached_response(cache_key)
    if cached_response.is_found:
        return cached_response.value
    try:
        api = EdxRestApiClient(site.siteconfiguration.enterprise_api_url, jwt=user.access_token)
        endpoint = getattr(api, api_resource_name)
        query_params = {
            'permissions': [settings.ENTERPRISE_DATA_API_GROUP],
            'enterprise_id': enterprise_id,
        }
        response = endpoint.with_access_to.get(**query_params)
    except (ConnectionError, SlumberHttpBaseException, Timeout) as exc:
        logger.warning('Unable to retrieve Enterprise Customer with_access_to details for user: %s: %r',
                       user.username, exc)
        return None
    if response.get('results', None) is None or response['count'] == 0:
        logger.warning('Unable to process Enterprise Customer with_access_to details for user: %s, enterprise: %s'
                       ' No Results Found', user.username, enterprise_id)
        return None
    if response['count'] > 1:
        logger.warning('Multiple Enterprise Customers found for user: %s, enterprise: %s', user.username, enterprise_id)
        return None
    TieredCache.set_all_tiers(cache_key, response['results'][0], settings.ENTERPRISE_API_CACHE_TIMEOUT)
    return response['results'][0]
