"""Functions used for data retrieval and manipulation by the API."""
from oscar.core.loading import get_model, get_class

from ecommerce.extensions.api import errors


Basket = get_model('basket', 'Basket')
Product = get_model('catalogue', 'Product')
ShippingEventType = get_model('order', 'ShippingEventType')

Selector = get_class('partner.strategy', 'Selector')


def get_basket(user):
    """Retrieve the basket belonging to the indicated user.

    If no such basket exists, create a new one. If multiple such baskets exist,
    merge them into one.
    """
    editable_baskets = Basket.objects.filter(owner=user, status__in=Basket.editable_statuses)
    if len(editable_baskets) == 0:
        basket = Basket.objects.create(owner=user)
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
        raise errors.ProductNotFoundError(
            errors.PRODUCT_NOT_FOUND_DEVELOPER_MESSAGE.format(sku=sku)
        )


def get_shipping_event_type(name):
    """Retrieve the shipping event type corresponding to the provided name."""
    try:
        return ShippingEventType.objects.get(name=name)
    except ShippingEventType.DoesNotExist:
        raise errors.ShippingEventNotFoundError(
            errors.SHIPPING_EVENT_NOT_FOUND_MESSAGE.format(name=name)
        )
