"""Exceptions and error messages used by the API."""
from django.utils.translation import ugettext_lazy as _


SKU_NOT_FOUND_DEVELOPER_MESSAGE = u"No SKU present in POST data"
SKU_NOT_FOUND_USER_MESSAGE = _("We couldn't find the identification code necessary to look up your product.")
PRODUCT_NOT_FOUND_DEVELOPER_MESSAGE = u"Catalog does not contain the indicated product [SKU: {sku}]"
PRODUCT_NOT_FOUND_USER_MESSAGE = _("We couldn't find the product you're looking for.")
SHIPPING_EVENT_NOT_FOUND_MESSAGE = u"No shipping event [{name}] was found"
PRODUCT_UNAVAILABLE_USER_MESSAGE = _("The product you're trying to order is unavailable.")


class ApiError(Exception):
    """Standard error raised by the API."""
    pass


class OrderError(ApiError):
    """Standard error raised by the orders endpoint.

    Indicative of a general error when attempting to add a product to the
    user's basket or turning that basket into an order.
    """
    pass


class ProductNotFoundError(OrderError):
    """Raised when the provided SKU does not correspond to a product in the catalog."""
    pass


class ShippingEventNotFoundError(OrderError):
    """Raised when a shipping event cannot be found by name."""
    pass
