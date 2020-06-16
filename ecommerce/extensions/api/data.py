"""Functions used for data retrieval and manipulation by the API."""


import logging

from oscar.core.loading import get_class, get_model

from ecommerce.extensions.api import exceptions

NoShippingRequired = get_class('shipping.methods', 'NoShippingRequired')
OrderTotalCalculator = get_class('checkout.calculators', 'OrderTotalCalculator')
Product = get_model('catalogue', 'Product')


logger = logging.getLogger(__name__)


def get_product(sku):
    """Retrieve the product corresponding to the provided SKU."""
    try:
        return Product.objects.get(stockrecords__partner_sku=sku)
    except Product.DoesNotExist:
        raise exceptions.ProductNotFoundError(
            exceptions.PRODUCT_NOT_FOUND_DEVELOPER_MESSAGE.format(sku=sku)
        )


def get_order_metadata(basket):
    """Retrieve information required to place an order.

    Arguments:
        basket (Basket): The basket whose contents are to be ordered.

    Returns:
        dict: Containing an order number, a shipping method, a shipping charge,
            and a Price object representing the order total.
    """
    shipping_method = NoShippingRequired()
    shipping_charge = shipping_method.calculate(basket)
    total = OrderTotalCalculator().calculate(basket, shipping_charge)

    metadata = {
        'number': basket.order_number,
        'shipping_method': shipping_method,
        'shipping_charge': shipping_charge,
        'total': total,
    }

    return metadata
