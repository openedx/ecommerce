import logging

from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from oscar.core.loading import get_class, get_model

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
    be added to the remaining open basket. If a voucher is passed, all existing
    ones added to the basket are removed because we allow only one voucher per
    basket after the Voucher is applied to the basket.

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
    if voucher:
        for v in basket.vouchers.all():
            basket.vouchers.remove(v)
        basket.vouchers.add(voucher)
        Applicator().apply(basket, request.user, request)
        logger.info('Applied Voucher [%s] to basket [%s].', voucher.code, basket.id)

    affiliate_id = request.COOKIES.get(settings.AFFILIATE_COOKIE_KEY)
    if affiliate_id:
        Referral.objects.update_or_create(
            basket=basket,
            defaults={'affiliate_id': affiliate_id}
        )
    else:
        Referral.objects.filter(basket=basket).delete()

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
