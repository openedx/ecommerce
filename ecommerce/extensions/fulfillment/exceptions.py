"""Exceptions and error messages used by the fulfillment module."""


class FulfillmentError(Exception):
    """Standard error for the fulfillment module.

    Indicates there was a general error with fulfillment or revoking a product.
    """


class FulfillmentConfigurationError(FulfillmentError):
    """Error for when the fulfillment module is improperly configured.

    Indicates that the setup of the fulfillment module is incorrect. This is likely due to tan incorrect
    mapping of FulfillmentModules to Product Types.
    """


class IncorrectOrderStatusError(FulfillmentError):
    """Error indicating the Order status cannot be fulfilled.

    Only orders in the current status can be moved to "Complete" or "Fulfillment Error". As such, it cannot
    move a "Refunded" or "Open" Order to "Complete", i.e. fulfilling it.
    """
