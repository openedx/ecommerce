"""Functions used for data retrieval and manipulation by the API."""
from oscar.core.loading import get_model, get_class

from ecommerce.extensions.api import exceptions
from ecommerce.extensions.api.constants import APIConstants as AC

Basket = get_model('basket', 'Basket')
Product = get_model('catalogue', 'Product')

Selector = get_class('partner.strategy', 'Selector')
NoShippingRequired = get_class('shipping.methods', 'NoShippingRequired')
OrderTotalCalculator = get_class('checkout.calculators', 'OrderTotalCalculator')


def get_basket(user, partner):
    """Retrieve the basket belonging to the indicated user and partner.

    If no such basket exists, create a new one. If multiple such baskets exist,
    merge them into one.
    """

    editable_baskets = Basket.objects.filter(owner=user, partner=partner, status__in=Basket.editable_statuses)
    if len(editable_baskets) == 0:
        basket = Basket.objects.create(owner=user, partner=partner)
    else:
        stale_baskets = list(editable_baskets)
        basket = stale_baskets.pop(0)
        for stale_basket in stale_baskets:
            # Don't add line quantities when merging baskets
            basket.merge(stale_basket, add_quantities=False)

    # Assign the appropriate strategy class to the basket
    basket.strategy = Selector().strategy(user=user)

    return basket


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
        AC.KEYS.ORDER_NUMBER: basket.order_number,
        AC.KEYS.SHIPPING_METHOD: shipping_method,
        AC.KEYS.SHIPPING_CHARGE: shipping_charge,
        AC.KEYS.ORDER_TOTAL: total,
    }

    return metadata
