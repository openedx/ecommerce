"""
Experimentation utilities
"""

import hashlib
import logging
import re

from ecommerce.enterprise.utils import get_enterprise_id_for_user
from ecommerce.extensions.analytics.utils import track_segment_event

logger = logging.getLogger(__name__)

SKUS_IN_EXPERIMENT = ['153FAFD', 'A4FAEAF', '705319F', '5F12E4E', '17B30DB', '6E5813C', 'A23979E']


def _is_eligible_for_REV1074_experiment(request, sku):
    """
    For https://openedx.atlassian.net/browse/REV-1074 we are testing a mostly hardcoded version of the checkout page.
    We are trying to improve performance and measure if there is an effect on revenue.
    In order to improve performance and simplify the engineering work, many use cases are not being handled.
    These use cases will all need to be omitted from the experiment and sent to the regular checkout page
    """
    basket = request.basket
    user_agent = request.META.get('HTTP_USER_AGENT')
    omit = (
        # We applied filters to our list of courses and only some courses will be included in the experiment
        sku not in SKUS_IN_EXPERIMENT or
        # The static page doesn't support offers/coupons so baskets with either are omitted from the experiment
        basket.applied_offers() or
        basket.voucher_discounts or
        basket.total_discount or
        # Optimizely is being used by the mobile app on the checkout page.
        # We are removing optimizely from the static version of the page,
        # so we are omitting mobile app traffic from this experiment
        (user_agent and re.search(r'edX/org.edx.mobile', user_agent)) or
        # Bundles would add substantial additional complexity to the experiment so we are omitting bundles
        basket.num_items > 1 or
        # The static page only supports seat products
        not basket.lines.first().product.is_seat_product or
        # The static page is not supporting enterprise use cases so enterprise learners need to be excluded
        # Excluding all offers and coupons above should handle most enterprise use cases
        # This check should handle enterprise users
        getattr(request.basket, 'ENTERPRISE_CATALOG_ATTRIBUTE_TYPE', None) or
        get_enterprise_id_for_user(basket.site, basket.owner) or
        # We do not want to include zero dollar purchases
        request.basket.total_incl_tax == 0 or
        str(request.user.username).startswith('test_') and str(request.user.email).endswith('example.com')
    )
    return not omit


def add_REV1074_information_to_url_if_eligible(redirect_url, request, sku):
    """
    For https://openedx.atlassian.net/browse/REV-1074 we are testing a mostly hardcoded version of the checkout page.
    We are trying to improve performance and measure if there is an effect on revenue.
    Here we determine which users are eligible to be in the experiment, then bucket the users
    into a treatment and control group, and send a log message to record this information for our experiment analysis
    """
    is_eligible_for_experiment = _is_eligible_for_REV1074_experiment(request, sku)
    bucket = stable_bucketing_hash_group('REV-1074', 2, request.user.username)
    route = bucket
    username = request.user.username
    basket = request.basket
    properties = {
        'experiment': 'static_checkout_page',
        'cart_id': basket.id
    }
    if not is_eligible_for_experiment:
        route = 0
        logger.info('REV1074: Should be omitted from experiment results: user [%s] with basket [%s].', username, basket)
        properties['bucket'] = 'not_in_experiment'
    elif is_eligible_for_experiment and bucket:
        logger.info('REV1074: Bucketed into treatment variation: user [%s] with basket [%s].', username, basket)
        properties['bucket'] = 'treatment'
    else:
        logger.info('REV1074: Bucketed into control variation: user [%s] with basket [%s].', username, basket)
        properties['bucket'] = 'control'

    track_segment_event(request.site, request.user, 'edx.bi.experiment.user.bucketed', properties)

    if route:
        redirect_url += sku + '.html'
    return redirect_url


def stable_bucketing_hash_group(group_name, group_count, username):
    """
    An implementation of a stable bucketing algorithm that can be used
    to reliably group users into experiments.

    Return the bucket that a user should be in for a given stable bucketing assignment.

    This function has been verified to return the same values as the stable bucketing
    functions in javascript and the master experiments table.

    Arguments:
        group_name: The name of the grouping/experiment.
        group_count: How many groups to bucket users into.
        username: The username of the user being bucketed.
    """
    hasher = hashlib.md5()
    hasher.update(group_name.encode('utf-8'))
    hasher.update(username.encode('utf-8'))
    hash_str = hasher.hexdigest()

    return int(re.sub('[8-9a-f]', '1', re.sub('[0-7]', '0', hash_str)), 2) % group_count
