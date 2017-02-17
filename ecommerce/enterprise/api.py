"""
Methods for fetching enterprise API data.
"""
from django.conf import settings
from django.core.cache import cache

from ecommerce.core.utils import get_cache_key


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

    entitlements = cache.get(cache_key)
    if not entitlements:
        api = site.siteconfiguration.enterprise_api_client
        entitlements = getattr(api, resource_url).get()
        cache.set(cache_key, entitlements, settings.ENTERPRISE_API_CACHE_TIMEOUT)

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
                            "name": "TestShib",
                            "catalog": 2,
                            "active": true,
                            "site": {
                                "domain": "example.com",
                                "name": "example.com"
                            },
                            "enable_data_sharing_consent": true,
                            "enforce_data_sharing_consent": "at_login",
                            "enterprise_customer_users": [
                                1
                            ],
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
                        "data_sharing_consent": [
                            {
                                "user": 1,
                                "state": "enabled",
                                "enabled": true
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

    response = cache.get(cache_key)
    if not response:
        api = site.siteconfiguration.enterprise_api_client
        endpoint = getattr(api, api_resource_name)
        querystring = {'username': user.username}
        response = endpoint().get(**querystring)
        cache.set(cache_key, response, settings.ENTERPRISE_API_CACHE_TIMEOUT)

    return response
