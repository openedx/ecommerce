"""
Helper methods for getting site based enterprise entitlements against the
learners.

Enterprise learners can get coupons, offered by their respective Enterprise
customers with which they are affiliated. The coupon product id's for the
enterprise entitlements are provided by the Enterprise Service on the basis
of the learner's enterprise eligibility criterion.
"""
import logging

from django.conf import settings
from django.core.cache import cache
from oscar.core.loading import get_model
from requests.exceptions import ConnectionError, Timeout
from slumber.exceptions import SlumberBaseException

from ecommerce.core.constants import COUPON_PRODUCT_CLASS_NAME
from ecommerce.core.utils import get_cache_key
from ecommerce.coupons.views import voucher_is_valid
from ecommerce.enterprise import api as enterprise_api
from ecommerce.enterprise.utils import is_enterprise_feature_enabled
from ecommerce.extensions.api.serializers import retrieve_all_vouchers

logger = logging.getLogger(__name__)
Product = get_model('catalogue', 'Product')
Voucher = get_model('voucher', 'Voucher')


def get_entitlement_voucher(request, product):
    """
    Returns entitlement voucher for the given product against an enterprise
    learner.

    Arguments:
        product (Product): A product that has course_id as attribute (seat or
            bulk enrollment coupon)
        request (HttpRequest): request with voucher data

    """
    if not is_enterprise_feature_enabled():
        return None

    vouchers = get_course_vouchers_for_learner(request.site, request.user, product.course_id)
    if not vouchers:
        return None

    entitlement_voucher = get_available_voucher_for_product(request, product, vouchers)
    return entitlement_voucher


def get_course_vouchers_for_learner(site, user, course_id):
    """
    Get vouchers against the list of all enterprise entitlements for the
    provided learner and course id.

    Arguments:
        course_id (str): The course ID.
        site: (django.contrib.sites.Site) site instance
        user: (django.contrib.auth.User) django auth user

    Returns:
        list of Voucher class objects

    """
    entitlements = get_course_entitlements_for_learner(site, user, course_id)
    if not entitlements:
        return None

    vouchers = []
    for entitlement in entitlements:
        try:
            coupon_product = Product.objects.filter(
                product_class__name=COUPON_PRODUCT_CLASS_NAME
            ).get(id=entitlement)
        except Product.DoesNotExist:
            logger.exception('There was an error getting coupon product with the entitlement id %s', entitlement)
            return None

        entitlement_voucher = retrieve_all_vouchers(coupon_product)
        vouchers.extend(entitlement_voucher)

    return vouchers


def get_course_entitlements_for_learner(site, user, course_id):
    """
    Get entitlements for the provided learner against the provided course id
    if the provided learner is affiliated with an enterprise.

    Arguments:
        course_id (str): The course ID.
        site: (django.contrib.sites.Site) site instance
        user: (django.contrib.auth.User) django auth user

    Returns:
        (list): List of entitlement ids, where entitlement id is actually a voucher id.
    """
    try:
        enterprise_learner_data = enterprise_api.fetch_enterprise_learner_data(site, user)['results']
    except (ConnectionError, SlumberBaseException, Timeout, KeyError, TypeError):
        logger.exception(
            'Failed to retrieve enterprise info for the learner [%s]',
            user.username
        )
        return None

    if not enterprise_learner_data:
        logger.info('Learner with username [%s] in not affiliated with any enterprise', user.username)
        return None

    try:
        enterprise_catalog_id = enterprise_learner_data[0]['enterprise_customer']['catalog']
        learner_id = enterprise_learner_data[0]['id']
    except KeyError:
        logger.exception('Invalid structure for enterprise learner API response for the learner [%s]', user.username)
        return None

    # Before returning entitlements verify that the provided course exists in
    # the enterprise course catalog
    if not is_course_in_enterprise_catalog(site, course_id, enterprise_catalog_id):
        return None

    try:
        entitlements = enterprise_api.fetch_enterprise_learner_entitlements(site, learner_id)
    except (ConnectionError, SlumberBaseException, Timeout):
        logger.exception(
            'Failed to retrieve entitlements for enterprise learner [%s].',
            learner_id
        )
        return None

    try:
        entitlements = [item['entitlement_id'] for item in entitlements['entitlements']]
    except KeyError:
        logger.exception(
            'Invalid structure for enterprise learner entitlements API response for enterprise learner [%s].',
            learner_id,
        )
        return None

    return entitlements


def is_course_in_enterprise_catalog(site, course_id, enterprise_catalog_id):
    """
    Verify that the provided course id exists in the site base list of course
    run keys from the provided enterprise course catalog.

    Arguments:
        course_id (str): The course ID.
        site: (django.contrib.sites.Site) site instance
        enterprise_catalog_id (Int): Course catalog id of enterprise

    Returns:
        Boolean

    """
    partner_code = site.siteconfiguration.partner.short_code
    cache_key = get_cache_key(
        site_domain=site.domain,
        partner_code=partner_code,
        resource='catalogs.contains',
        course_id=course_id,
        catalog_id=enterprise_catalog_id
    )
    response = cache.get(cache_key)
    if not response:
        try:
            # GET: /api/v1/catalogs/{catalog_id}/contains?course_run_id={course_run_ids}
            response = site.siteconfiguration.course_catalog_api_client.catalogs(enterprise_catalog_id).contains.get(
                course_run_id=course_id
            )
            cache.set(cache_key, response, settings.COURSES_API_CACHE_TIMEOUT)
        except (ConnectionError, SlumberBaseException, Timeout):
            logger.exception('Unable to connect to Course Catalog service for catalog contains endpoint.')
            return False

    try:
        return response['courses'][course_id]
    except KeyError:
        return False


def get_available_voucher_for_product(request, product, vouchers):
    """
    Get first active entitlement from a list of vouchers for the given
    product.

    Arguments:
        product (Product): A product that has course_id as attribute (seat or
            bulk enrollment coupon)
        request (HttpRequest): request with voucher data
        vouchers: (List) List of voucher class objects for an enterprise

    """
    for voucher in vouchers:
        is_valid_voucher, __ = voucher_is_valid(voucher, [product], request)
        if is_valid_voucher:
            voucher_offer = voucher.offers.first()
            offer_range = voucher_offer.condition.range
            if offer_range.contains_product(product):
                return voucher

    # Explicitly return None in case product has no valid voucher
    return None
