import datetime
import json
import logging
from urllib import unquote, urlencode

import newrelic.agent
import pytz
from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.utils.translation import ugettext_lazy as _
from oscar.core.loading import get_class, get_model

from ecommerce.courses.utils import mode_for_product
from ecommerce.extensions.order.exceptions import AlreadyPlacedOrderException
from ecommerce.extensions.order.utils import UserAlreadyPlacedOrder
from ecommerce.extensions.payment.utils import embargo_check
from ecommerce.referrals.models import Referral

Applicator = get_class('offer.applicator', 'Applicator')
Basket = get_model('basket', 'Basket')
BasketAttribute = get_model('basket', 'BasketAttribute')
BasketAttributeType = get_model('basket', 'BasketAttributeType')
BUNDLE = 'bundle_identifier'
ORGANIZATION_ATTRIBUTE_TYPE = 'organization'
ENTERPRISE_CATALOG_ATTRIBUTE_TYPE = 'enterprise_catalog_uuid'
StockRecord = get_model('partner', 'StockRecord')
OrderLine = get_model('order', 'Line')
Refund = get_model('refund', 'Refund')

logger = logging.getLogger(__name__)


def add_utm_params_to_url(url, params):
    # utm_params is [(u'utm_content', u'course-v1:IDBx IDB20.1x 1T2017'),...
    utm_params = [item for item in params if 'utm_' in item[0]]
    # utm_params is utm_content=course-v1%3AIDBx+IDB20.1x+1T2017&...
    utm_params = urlencode(utm_params, True)
    # utm_params is utm_content=course-v1:IDBx+IDB20.1x+1T2017&...
    # (course-keys do not have url encoding)
    utm_params = unquote(utm_params)
    url = url + '?' + utm_params if utm_params else url
    return url


def prepare_basket(request, products, voucher=None):
    """
    Create or get the basket, add products, apply a voucher, and record referral data.

    Existing baskets are merged. Specified products will
    be added to the remaining open basket. If voucher is passed, all existing
    vouchers added to the basket are removed because we allow only one voucher per basket.
    Vouchers are not applied if an enrollment code product is in the basket.

    Arguments:
        request (Request): The request object made to the view.
        products (List): List of products to be added to the basket.
        voucher (Voucher): Voucher to apply to the basket.

    Returns:
        basket (Basket): Contains the product to be redeemed and the Voucher applied.
    """
    basket = Basket.get_basket(request.user, request.site)
    basket_add_enterprise_catalog_attribute(basket, request.GET)
    basket.flush()
    basket.save()
    basket_addition = get_class('basket.signals', 'basket_addition')
    already_purchased_products = []
    bundle = request.GET.get('bundle')

    _set_basket_bundle_status(bundle, basket)

    if request.site.siteconfiguration.enable_embargo_check:
        if not embargo_check(request.user, request.site, products):
            messages.error(
                request,
                _('Due to export controls, we cannot allow you to access this course at this time.')
            )
            logger.warning(
                'User [%s] blocked by embargo check, not adding products to basket',
                request.user.username
            )
            return basket

    is_multi_product_basket = True if len(products) > 1 else False
    for product in products:
        if product.is_enrollment_code_product or \
                not UserAlreadyPlacedOrder.user_already_placed_order(user=request.user,
                                                                     product=product, site=request.site):
            basket.add_product(product, 1)
            # Call signal handler to notify listeners that something has been added to the basket
            basket_addition.send(sender=basket_addition, product=product, user=request.user, request=request,
                                 basket=basket, is_multi_product_basket=is_multi_product_basket)
        else:
            already_purchased_products.append(product)
            logger.warning(
                'User [%s] attempted to repurchase the [%s] seat of course [%s]',
                request.user.username,
                mode_for_product(product),
                product.course_id
            )
    if already_purchased_products and basket.is_empty:
        raise AlreadyPlacedOrderException

    if len(products) == 1 and products[0].is_enrollment_code_product:
        basket.clear_vouchers()
    elif voucher:
        basket.clear_vouchers()
        basket.vouchers.add(voucher)
        Applicator().apply(basket, request.user, request)
        logger.info('Applied Voucher [%s] to basket [%s].', voucher.code, basket.id)

    attribute_cookie_data(basket, request)
    return basket


def get_basket_switch_data(product):
    """
    Given a seat or enrollment product, find the SKU of the related product of
    the other type, along with the text to display to the user for the
    toggle link.  This is used on the Basket Summary page to enable users to
    switch between purchasing a single course run Seat and making a bulk
    purchase of a set of Enrollment Codes for the same course run.

    Arguments:
        product (Product): Product of type Seat or Enrollment Code

    Returns:
        tuple(str, str): containing the link display text and associated sku
    """
    switch_link_text = None
    partner_sku = None

    if product.is_enrollment_code_product:
        partner_sku = _find_seat_enrollment_toggle_sku(product, 'child')
        switch_link_text = _('Click here to just purchase an enrollment for yourself')
    elif product.is_seat_product:
        partner_sku = _find_seat_enrollment_toggle_sku(product, 'standalone')
        switch_link_text = _('Click here to purchase multiple seats in this course')

    return switch_link_text, partner_sku


def _find_seat_enrollment_toggle_sku(product, target_structure):
    """
    Given a seat or enrollment code product, find the SKU of the related product of
    the other type that matches the target structure.

    Arguments:
        product (Product): Product of type Seat or Enrollment Code
        target_structure (str): Structure of the related product we're seeking

    Returns:
        sku (str): The sku of the associated Seat or Enrollment Code product.
    """

    # Note: This query filter will not perform well with products that do not have a course_id
    stock_records = StockRecord.objects.filter(
        product__course_id=product.course_id,
        product__structure=target_structure
    )

    # Determine the proper partner SKU to embed in the single/multiple basket switch link
    # The logic here is a little confusing.  "Seat" products have "certificate_type" attributes, and
    # "Enrollment Code" products have "seat_type" attributes.  If the basket is in single-purchase
    # mode, we are working with a Seat product and must present the 'buy multiple' switch link and
    # SKU from the corresponding Enrollment Code product.  If the basket is in multi-purchase mode,
    # we are working with an Enrollment Code product and must present the 'buy single' switch link
    # and SKU from the corresponding Seat product.
    product_cert_type = getattr(product.attr, 'certificate_type', None)
    product_seat_type = getattr(product.attr, 'seat_type', None)
    for stock_record in stock_records:
        stock_record_cert_type = getattr(stock_record.product.attr, 'certificate_type', None)
        stock_record_seat_type = getattr(stock_record.product.attr, 'seat_type', None)
        if (product_seat_type and product_seat_type == stock_record_cert_type) or \
                (product_cert_type and product_cert_type == stock_record_seat_type):
            return stock_record.partner_sku

    return None


def attribute_cookie_data(basket, request):
    try:
        with transaction.atomic():
            # If an exception is raised below, this nested atomic block prevents the
            # outer transaction created by ATOMIC_REQUESTS from being rolled back.
            referral = _referral_from_basket_site(basket, request.site)

            _record_affiliate_basket_attribution(referral, request)
            _record_utm_basket_attribution(referral, request)

            # Save the record if any attribution attributes are set on it.
            if any([getattr(referral, attribute) for attribute in Referral.ATTRIBUTION_ATTRIBUTES]):
                referral.save()
            # Clean up the record if no attribution attributes are set and it exists in the DB.
            elif referral.pk:
                referral.delete()
            # Otherwise we can ignore the instantiated but unsaved referral

    # Don't let attribution errors prevent users from creating baskets
    except:  # pylint: disable=broad-except, bare-except
        logger.exception('Error while attributing cookies to basket.')


def _referral_from_basket_site(basket, site):
    try:
        # There should be only 1 referral instance for one basket.
        # Referral and basket has a one to one relationship
        referral = Referral.objects.get(basket=basket)
    except Referral.DoesNotExist:
        referral = Referral(basket=basket, site=site)
    return referral


def _record_affiliate_basket_attribution(referral, request):
    """
      Attribute this user's basket to the referring affiliate, if applicable.
    """

    # TODO: update this line to use site configuration once config in production (2016-10-04)
    # affiliate_cookie_name = request.site.siteconfiguration.affiliate_cookie_name
    # affiliate_id = request.COOKIES.get(affiliate_cookie_name)

    affiliate_id = request.COOKIES.get(settings.AFFILIATE_COOKIE_KEY, "")
    referral.affiliate_id = affiliate_id


def _record_utm_basket_attribution(referral, request):
    """
      Attribute this user's basket to UTM data, if applicable.
    """
    utm_cookie_name = request.site.siteconfiguration.utm_cookie_name
    utm_cookie = request.COOKIES.get(utm_cookie_name, "{}")
    utm = json.loads(utm_cookie)

    for attr_name in ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content']:
        setattr(referral, attr_name, utm.get(attr_name, ""))

    created_at_unixtime = utm.get('created_at')
    if created_at_unixtime:
        # We divide by 1000 here because the javascript timestamp generated is in milliseconds not seconds.
        # PYTHON: time.time()      => 1475590280.823698
        # JS: new Date().getTime() => 1475590280823
        created_at_datetime = datetime.datetime.fromtimestamp(int(created_at_unixtime) / float(1000), tz=pytz.UTC)
    else:
        created_at_datetime = None

    referral.utm_created_at = created_at_datetime


def basket_add_organization_attribute(basket, request_data):
    """
    Add organization attribute on basket, if organization value is provided
    in basket data.

    Arguments:
        basket(Basket): order basket
        request_data (dict): HttpRequest data

    """
    # Name of business client is being passed as "organization" from basket page
    business_client = request_data.get(ORGANIZATION_ATTRIBUTE_TYPE)

    if business_client:
        organization_attribute, __ = BasketAttributeType.objects.get_or_create(name=ORGANIZATION_ATTRIBUTE_TYPE)
        BasketAttribute.objects.get_or_create(
            basket=basket,
            attribute_type=organization_attribute,
            value_text=business_client.strip()
        )


@newrelic.agent.function_trace()
def basket_add_enterprise_catalog_attribute(basket, request_data):
    """
    Add enterprise catalog UUID attribute on basket, if the catalog UUID value
    is provided in the request.

    Arguments:
        basket(Basket): order basket
        request_data (dict): HttpRequest data

    """
    # Value of enterprise catalog UUID is being passed as `catalog` from
    # basket page
    enterprise_catalog_uuid = request_data.get('catalog') if request_data else None
    enterprise_catalog_attribute, __ = BasketAttributeType.objects.get_or_create(
        name=ENTERPRISE_CATALOG_ATTRIBUTE_TYPE
    )
    if enterprise_catalog_uuid:
        BasketAttribute.objects.update_or_create(
            basket=basket,
            attribute_type=enterprise_catalog_attribute,
            defaults={
                'value_text': enterprise_catalog_uuid.strip()
            }
        )
    else:
        # Remove the enterprise catalog attribute for future update in basket
        BasketAttribute.objects.filter(basket=basket, attribute_type=enterprise_catalog_attribute).delete()


def _set_basket_bundle_status(bundle, basket):
    """
    Sets the basket's bundle status

    Note: This is a refactor of the existing code. Not sure
    what the intentions of the side effects are.

    Side effect:
        clears any vouchers if it's a bundle

    Args:
        bundle (str): The Bundle ID?
        basket (Basket): The basket to set the bundle attribute for

    Returns:

    """
    if bundle:
        BasketAttribute.objects.update_or_create(
            basket=basket,
            attribute_type=BasketAttributeType.objects.get(name=BUNDLE),
            defaults={'value_text': bundle}
        )
        basket.clear_vouchers()
    else:
        BasketAttribute.objects.filter(basket=basket, attribute_type__name=BUNDLE).delete()
