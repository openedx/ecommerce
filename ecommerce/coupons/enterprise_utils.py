"""
Enterprise related utility functions.
"""
import logging

from django.conf import settings
from django.core.cache import cache


log = logging.getLogger(__name__)


def get_user_enterprise_info(user, site):
    """
    Get the Enterprise for the given learner along with the entitlement info.

    Arguments:
        user (django.contrib.auth.User): django auth user
        site (django.contrib.sites.Site): site instance
    """
    # TODO: Fetch learner related enterprise info from Enterprise API against a specific site
    # response = {}
    # try:
    #     response = site.siteconfiguration.enterprise_api_client.course_runs.get(user.username, site.domain)
    # except (ConnectionError, SlumberBaseException, Timeout):
    #     log.exception(
    #         'Failed to retrieve enterprise info for the learner [%s]',
    #         user.username
    #     )
    #     raise

    # create dummy data for testing
    response = {
        'username': user.username,
        'enterprise': {
            'name': 'Arbisoft',
            'catalog': 1,
            'site_domain': site.domain,
            'enable_data_sharing_consent': True,
            'enforce_data_sharing_consent': 'At Enrollment',
            'logo': 'https://www.edx.org/sites/default/files/homepage/banner/promo/bkg/onethird-539x290-csedweek.jpg',
            'user_data_sharing_consent': True
        }
    }
    # TODO: Cache the response from enterprise API in case of 200 status
    return response
