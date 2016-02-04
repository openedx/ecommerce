import logging

from oscar.core.loading import get_class, get_model

Applicator = get_class('offer.utils', 'Applicator')
Basket = get_model('basket', 'Basket')
logger = logging.getLogger(__name__)
Selector = get_class('partner.strategy', 'Selector')
StockRecord = get_model('partner', 'StockRecord')
Voucher = get_model('voucher', 'Voucher')


def prepare_basket(request, user, product, voucher=None):
    """
    Prepare the basket, add the product, and apply a voucher.

    Existing baskets are merged and flushed. The specified product will
    be added to the remaining open basket, and the basket will be frozen.
    The Voucher is applied to the basket and checked for discounts.

    Arguments:
    site (Site): The site from which the request came.
    user (User): User who made the request.
    product (Product): Product to be added to the basket.
    voucher (Voucher): Voucher to apply to the basket.

    Returns:
    basket (Basket): Contains the product to be redeemed and the Voucher applied.
    """
    basket = Basket.get_basket(user, request.site)
    # remove all existing vouchers from the basket
    for v in basket.vouchers.all():
        basket.vouchers.remove(v)
    basket.reset_offer_applications()
    basket.flush()
    basket.add_product(product, 1)
    if voucher:
        basket.vouchers.add(voucher)
        Applicator().apply(basket, user, request)
        logger.info('Applied Voucher [%s] to basket.', voucher.code)

    return basket


def get_product_from_sku(partner, sku):
    """
    Looks up a product stock record for a given partner/sku

    Arguments:
    partner: The partner that the product belongs.
    sku: The sku for the product to lookup.

    Returns:
    Product: The product that matches the sku.
    Msg: An error message if the product is not found.
    """
    try:
        stock_record = StockRecord.objects.get(partner=partner, partner_sku=sku)
    except StockRecord.DoesNotExist:
        msg = 'SKU [{sku}] does not exist for partner [{name}].'.format(sku=sku, name=partner.name)
        return None, msg

    return stock_record.product, None
