import datetime
import json
import logging

from django.conf import settings
from django.db import transaction
from django.utils.translation import ugettext_lazy as _
from oscar.core.loading import get_class, get_model
import pytz

from ecommerce.core.constants import ENROLLMENT_CODE_PRODUCT_CLASS_NAME, SEAT_PRODUCT_CLASS_NAME
from ecommerce.referrals.models import Referral

Applicator = get_class('offer.utils', 'Applicator')
Basket = get_model('basket', 'Basket')
StockRecord = get_model('partner', 'StockRecord')

logger = logging.getLogger(__name__)


def prepare_basket(request, product, voucher=None):
    """
    Create or get the basket, add the product, apply a voucher, and record referral data.

    Existing baskets are merged. The specified product will
    be added to the remaining open basket. If voucher is passed, all existing
    vouchers added to the basket are removed because we allow only one voucher per basket.
    Vouchers are not applied if an enrollment code product is in the basket.

    Arguments:
        request (Request): The request object made to the view.
        product (Product): Product to be added to the basket.
        voucher (Voucher): Voucher to apply to the basket.

    Returns:
        basket (Basket): Contains the product to be redeemed and the Voucher applied.
    """
    basket = Basket.get_basket(request.user, request.site)
    basket.flush()
    basket.add_product(product, 1)
    if product.get_product_class().name == ENROLLMENT_CODE_PRODUCT_CLASS_NAME:
        basket.clear_vouchers()
    elif voucher:
        basket.clear_vouchers()
        basket.vouchers.add(voucher)
        Applicator().apply(basket, request.user, request)
        logger.info('Applied Voucher [%s] to basket [%s].', voucher.code, basket.id)

    attribute_cookie_data(basket, request)

    # Call signal handler to notify listeners that something has been added to the basket
    basket_addition = get_class('basket.signals', 'basket_addition')
    basket_addition.send(sender=basket_addition, product=product, user=request.user, request=request, basket=basket)

    return basket


def get_basket_switch_data(product):
    product_class_name = product.get_product_class().name

    if product_class_name == ENROLLMENT_CODE_PRODUCT_CLASS_NAME:
        switch_link_text = _('Click here to just purchase an enrollment for yourself')
        structure = 'child'
    elif product_class_name == SEAT_PRODUCT_CLASS_NAME:
        switch_link_text = _('Click here to purchase multiple seats in this course')
        structure = 'standalone'

    stock_records = StockRecord.objects.filter(
        product__course_id=product.course_id,
        product__structure=structure
    )

    # Determine the proper partner SKU to embed in the single/multiple basket switch link
    # The logic here is a little confusing.  "Seat" products have "certificate_type" attributes, and
    # "Enrollment Code" products have "seat_type" attributes.  If the basket is in single-purchase
    # mode, we are working with a Seat product and must present the 'buy multiple' switch link and
    # SKU from the corresponding Enrollment Code product.  If the basket is in multi-purchase mode,
    # we are working with an Enrollment Code product and must present the 'buy single' switch link
    # and SKU from the corresponding Seat product.
    partner_sku = None
    product_cert_type = getattr(product.attr, 'certificate_type', None)
    product_seat_type = getattr(product.attr, 'seat_type', None)
    for stock_record in stock_records:
        stock_record_cert_type = getattr(stock_record.product.attr, 'certificate_type', None)
        stock_record_seat_type = getattr(stock_record.product.attr, 'seat_type', None)
        if (product_seat_type and product_seat_type == stock_record_cert_type) or \
           (product_cert_type and product_cert_type == stock_record_seat_type):
            partner_sku = stock_record.partner_sku
            break
    return switch_link_text, partner_sku


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
