from decimal import Decimal
import logging

from django.db.utils import IntegrityError

from oscar.core.loading import get_model

from ecommerce.extensions.catalogue.utils import generate_coupon_slug, generate_sku
from ecommerce.extensions.voucher.models import CouponVouchers
from ecommerce.extensions.voucher.utils import create_vouchers as utils_create_vouchers

logger = logging.getLogger(__name__)

Product = get_model('catalogue', 'Product')
ProductCategory = get_model('catalogue', 'ProductCategory')
ProductClass = get_model('catalogue', 'ProductClass')
StockRecord = get_model('partner', 'StockRecord')


def create_coupon_product(title, price, data):
    """Creates a coupon product and a stock record for it.

    Arguments:
        title (str): The name of the coupon.
        price (int): The price of the coupon(s).
        data (dict): Contains data needed to create vouchers,SKU and UPC:
            - partner (User)
            - benefit_type (str)
            - benefit_value (int)
            - catalog (Catalog)
            - end_date (Datetime)
            - code (str)
            - quantity (int)
            - start_date (Datetime)
            - voucher_type (str)
            - categories (list of Category objects)
            - note (str)
            - max_uses (int)

    Returns:
        A coupon product object.

    Raises:
        IntegrityError: An error occured when create_vouchers method returns
                        an IntegrityError exception
    """
    coupon_slug = generate_coupon_slug(title=title, catalog=data['catalog'], partner=data['partner'])
    defaults = {'requires_shipping': False, 'track_stock': False, 'name': 'Coupon'}
    product_class, __ = ProductClass.objects.get_or_create(slug='coupon', defaults=defaults)
    coupon_product, __ = Product.objects.get_or_create(
        title=title,
        product_class=product_class,
        slug=coupon_slug
    )

    for category in data['categories']:
        ProductCategory.objects.get_or_create(product=coupon_product, category=category)

    # Vouchers are created during order and not fulfillment like usual
    # because we want vouchers to be part of the line in the order.
    if data.get('create_vouchers', False):
        try:
            utils_create_vouchers(
                name=title,
                benefit_type=data['benefit_type'],
                benefit_value=Decimal(data['benefit_value']),
                catalog=data['catalog'],
                coupon=coupon_product,
                end_datetime=data['end_date'],
                code=data['code'] or None,
                quantity=int(data['quantity']),
                start_datetime=data['start_date'],
                voucher_type=data['voucher_type'],
                max_uses=data['max_uses'],
                coupon_id=coupon_product.id
            )
            coupon_vouchers = CouponVouchers.objects.get(coupon=coupon_product)
            coupon_product.attr.coupon_vouchers = coupon_vouchers

        except IntegrityError as ex:
            logger.exception('Failed to create vouchers for [%s] coupon.', coupon_product.title)
            raise IntegrityError(ex)  # pylint: disable=nonstandard-exception

    coupon_product.attr.note = data['note']
    coupon_product.save()

    sku = generate_sku(
        product=coupon_product,
        partner=data['partner'],
        catalog=data['catalog'],
    )

    stock_record, __ = StockRecord.objects.get_or_create(
        product=coupon_product,
        partner=data['partner'],
        partner_sku=sku
    )
    stock_record.price_currency = 'USD'
    stock_record.price_excl_tax = price
    stock_record.save()

    return coupon_product
