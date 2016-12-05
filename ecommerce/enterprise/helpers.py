"""
Helper methods for enterprise app.
"""
import logging
from edx_rest_api_client.client import EdxRestApiClient
from requests.exceptions import ConnectionError, Timeout
from slumber.exceptions import SlumberBaseException

log = logging.getLogger(__name__)


def get_learner_info(user, site):
    """
    Fetch user and its enterprise data from lms.

    Args:
        user: (django.contrib.auth.User) django auth user
        site: (django.contrib.sites.Site) site instance
    """
    # We can also add another method (build_enterprise_url) specifically for building enterprise related urls
    # This would be useful when we move enterprise to a separated IDA
    api_url = site.siteconfiguration.build_enterprise_url('/api/enterprise/v1/')

    try:
        api = EdxRestApiClient(
            api_url,
            oauth_access_token=user.access_token,
            append_slash=False
        )
        response = api.learners(user.username).get()
        return response
    except (ConnectionError, SlumberBaseException, Timeout):
        log.exception(
            'Failed to retrieve learner details for [%s]',
            user.username
        )
        raise


def get_data_sharing_consent_info(learner, enterprise_customer, site):
    """
    Fetch data related to data sharing consent.
    Args:
        learner: (django.contrib.auth.User) django auth user
        enterprise_customer: (str) unique identifier for enterprise customer
        site: (django.contrib.sites.Site) site instance
    """
    api_url = site.siteconfiguration.build_enterprise_url('/api/enterprise/v1/')

    try:
        api = EdxRestApiClient(
            api_url,
            oauth_access_token=learner.access_token,
            append_slash=False
        )
        response = api.data_sharing_consent(learner=learner.username, enterprise_custome=enterprise_customer).get()
        return response
    except (ConnectionError, SlumberBaseException, Timeout):
        log.exception(
            'Failed to retrieve learner details for [%s]',
            learner.username
        )
        raise


def get_entitlements_info(user, site):
    """
    Get entitlement info for the given learner.

    Args:
        user: (django.contrib.auth.User) django auth user
        site: (django.contrib.sites.Site) site instance
    """
    learner = get_learner_info(user, site)
    enterprise_customer = learner.get("enterprise_customer")

    if enterprise_customer is None:
        # Learner not associated to any interprise customer,
        # proceed to the checkout
        raise ValueError("Learner does not have entitlements, proceed to checkout.")

    data_sharing = get_data_sharing_consent_info(learner, enterprise_customer, site)

    if data_sharing.get("enterprise_customer") == "required" and data_sharing.get("learner") != "agree":
        # display the following message to learner
        # "In order to get discount for course <course-id> you must consent to share your
        # data with <enterprise customer name>, If you do not consent to data sharing you
        # will still be able to enroll but you will not get any discounts from <enterprise customer name>"
        pass
    else:
        # Apply discount on the course and proceed to checkout
        pass
