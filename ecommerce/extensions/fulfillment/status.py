""" Contains all the available statuses for Orders and Order Lines """


class ORDER:
    """Constants representing all known order statuses. """
    COMPLETE = 'Complete'
    FULFILLMENT_ERROR = 'Fulfillment Error'
    PAYMENT_ERROR = 'Payment Error'
    OPEN = 'Open'
    PENDING = 'Pending'


class LINE:
    """Constants representing all known line statuses. """
    COMPLETE = 'Complete'
    FULFILLMENT_CONFIGURATION_ERROR = 'Fulfillment Configuration Error'
    FULFILLMENT_NETWORK_ERROR = 'Fulfillment Network Error'
    FULFILLMENT_TIMEOUT_ERROR = 'Fulfillment Timeout Error'
    FULFILLMENT_SERVER_ERROR = 'Fulfillment Server Error'
    OPEN = 'Open'
