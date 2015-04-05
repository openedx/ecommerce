""" Contains all the available statuses for Orders and Order Lines """


class ORDER(object):
    """Constants representing all known order statuses. """
    OPEN = 'Open'
    ORDER_CANCELLED = 'Order Cancelled'
    BEING_PROCESSED = 'Being Processed'
    PAYMENT_CANCELLED = 'Payment Cancelled'
    PAID = 'Paid'
    FULFILLMENT_ERROR = 'Fulfillment Error'
    COMPLETE = 'Complete'
    REFUNDED = 'Refunded'
    PAYMENT_ERROR = 'Payment Error'


class LINE(object):
    """Constants representing all known line statuses. """
    OPEN = 'Open'
    ORDER_CANCELLED = 'Order Cancelled'
    BEING_PROCESSED = 'Being Processed'
    PAYMENT_CANCELLED = 'Payment Cancelled'
    PAID = 'Paid'
    FULFILLMENT_CONFIGURATION_ERROR = 'Fulfillment Configuration Error'
    FULFILLMENT_NETWORK_ERROR = 'Fulfillment Network Error'
    FULFILLMENT_TIMEOUT_ERROR = 'Fulfillment Timeout Error'
    FULFILLMENT_SERVER_ERROR = 'Fulfillment Server Error'
    COMPLETE = 'Complete'
    REFUNDED = 'Refunded'
    REVOKE_CONFIGURATION_ERROR = 'Revoke Configuration Error'
    REVOKE_NETWORK_ERROR = 'Revoke Network Error'
    REVOKE_TIMEOUT_ERROR = 'Revoke Timeout Error'
    REVOKE_SERVER_ERROR = 'Revoke Server Error'
