"""Errors thrown by the Fulfillment API."""


class FulfillmentError(Exception):
    """ Standard error for the Fulfillment API.

    Indicates there was a general error with fulfillment or revoking a product.

    """
    pass


class FulfillmentConfigurationError(FulfillmentError):
    """ Error for when the Fulfillment API is improperly configured.

    Indicates that the setup of the Fulfillment API is incorrect. This is likely due to tan incorrect
    mapping of FulfillmentModules to Product Types.

    """
    pass


class IncorrectOrderStatusError(FulfillmentError):
    """ Error indicating the Order status cannot be fulfilled.

    Only orders in the current status can be moved to "Complete" or "Fulfillment Error". As such, it cannot
    move a "Refunded" or "Open" Order to "Complete", i.e. fulfilling it.

    """
    pass
