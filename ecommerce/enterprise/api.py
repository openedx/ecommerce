"""
Methods for fetching enterprise API data.
"""


import logging
from urllib.parse import urlencode

from django.conf import settings
from edx_django_utils.cache import TieredCache
from requests.exceptions import ConnectionError as ReqConnectionError
from requests.exceptions import Timeout
from slumber.exceptions import SlumberHttpBaseException

from ecommerce.core.utils import get_cache_key
from ecommerce.enterprise.utils import get_enterprise_id_for_current_request_user_from_jwt

logger = logging.getLogger(__name__)


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
                            }
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
    api = site.siteconfiguration.enterprise_catalog_api_client

    # Determine API resource to use
    api_resource_name = 'enterprise-customer'
    api_resource_id = enterprise_customer_uuid
    if enterprise_customer_catalog_uuid:
        api_resource_name = 'enterprise-catalogs'
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

    endpoint = getattr(api, api_resource_name)(api_resource_id)
    contains_content = endpoint.contains_content_items.get(**query_params)['contains_content_items']
    TieredCache.set_all_tiers(cache_key, contains_content, settings.ENTERPRISE_API_CACHE_TIMEOUT)

    return contains_content


def get_enterprise_id_for_user(site, user):
    enterprise_from_jwt = get_enterprise_id_for_current_request_user_from_jwt()
    if enterprise_from_jwt:
        return enterprise_from_jwt

    try:
        enterprise_learner_response = fetch_enterprise_learner_data(site, user)
    except (AttributeError, ReqConnectionError, KeyError, SlumberHttpBaseException, Timeout) as exc:
        logger.info('Unable to retrieve enterprise learner data for User: %s, Exception: %s', user, exc)
        return None

    try:
        return enterprise_learner_response['results'][0]['enterprise_customer']['uuid']
    except IndexError:
        pass

    return None
