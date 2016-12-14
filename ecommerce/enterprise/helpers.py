"""
Helper methods for enterprise app.
"""
import logging
import waffle

from django.conf import settings

from edx_rest_api_client.client import EdxRestApiClient
from requests.exceptions import ConnectionError, Timeout
from slumber.exceptions import SlumberBaseException
from oscar.core.loading import get_model

from ecommerce.coupons.views import voucher_is_valid
from ecommerce.enterprise.tmp import utils
from ecommerce.theming import helpers as theming_helpers

CouponVouchers = get_model('voucher', 'CouponVouchers')

log = logging.getLogger(__name__)


def is_enterprise_feature_enabled():
    """
    Returns boolean indicating whether enterprise feature is enabled or disabled.

    Example:
        >> is_enterprise_feature_enabled()
        True

    Returns:
         (bool): True if enterprise feature is enabled else False
    """

    # Return False if enterprise feature is disabled via Django settings
    if not settings.ENABLE_ENTERPRISES:
        return False

    # Return False if we're currently processing a request and enterprise feature is disabled via runtime switch
    if bool(theming_helpers.get_current_request()) and \
            waffle.switch_is_active(settings.DISABLE_ENTERPRISES_ON_RUNTIME_SWITCH):
        return False

    # Return True indicating enterprise feature is enabled
    return True


@utils.dummy_data("learner")
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


@utils.dummy_data("data_sharing")
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


@utils.dummy_data("entitlements")
def fetch_entitlements(learner, course, enterprise, site):
    """
    Fetch data related to enterprise entitlements.
    Args:
        learner: (django.contrib.auth.User) django auth user
        course: course for which to fetch entitlements
        enterprise: (str) unique identifier for enterprise customer
        site: (django.contrib.sites.Site) site instance
    """
    api_url = site.siteconfiguration.build_enterprise_url('/api/enterprise/v1/')

    try:
        api = EdxRestApiClient(
            api_url,
            oauth_access_token=learner.access_token,
            append_slash=False
        )
        response = api.entitlements(
            learner=learner.username, enterprise_custome=enterprise, course=course,
        ).get()
        return response
    except (ConnectionError, SlumberBaseException, Timeout):
        log.exception(
            'Failed to retrieve entitlements details for [%s]',
            learner.username
        )
        raise


def is_learner_eligible_for_entitlements(user, site):
    """
    Get entitlement info for the given learner.

    Returns True if learner is eligible for entitlements, False otherwise.

    Args:
        user: (django.contrib.auth.User) django auth user
        site: (django.contrib.sites.Site) site instance
    """

    learner = get_learner_info(user, site)
    enterprise_customer = learner.get("enterprise_customer")

    if enterprise_customer is None:
        # Learner not associated to any enterprise customer,
        # proceed to the checkout
        return False

    data_sharing = get_data_sharing_consent_info(learner, enterprise_customer, site)

    if data_sharing.get("enterprise_customer") == "required" and data_sharing.get("learner") != "agree":
        # display the following message to learner
        # "In order to get discount for course <course-id> you must consent to share your
        # data with <enterprise customer name>, If you do not consent to data sharing you
        # will still be able to enroll but you will not get any discounts from <enterprise customer name>"
        return False
    else:
        # Apply discount on the course and proceed to checkout
        return True


def get_entitlement_voucher(request, product):
    """
    Return entitlement voucher for the given learner.
    """

    if not is_learner_eligible_for_entitlements(request.user, request.site):
        return None

    learner = get_learner_info(request.user, request.site)
    enterprise_customer = learner.get("enterprise_customer")
    entitlement_ids = fetch_entitlements(request.user, product, enterprise_customer, request.site)

    coupon_vouchers = CouponVouchers.objects.filter(coupon__id__in=entitlement_ids)
    for coupon_voucher in coupon_vouchers:
        vouchers = [
            voucher for voucher in coupon_voucher.vouchers.all() if voucher_is_valid(voucher, [product], request)
        ]
        if len(vouchers) > 0:
            return vouchers[0]

    return None
