""" Contains all the available statuses for Orders and Order Lines """


class ORDER(object):
    """Constants representing all known order statuses. """
    COMPLETE = 'Complete'
    FULFILLMENT_ERROR = 'Fulfillment Error'
    OPEN = 'Open'


class LINE(object):
    """Constants representing all known line statuses. """
    COMPLETE = 'Complete'
    FULFILLMENT_CONFIGURATION_ERROR = 'Fulfillment Configuration Error'
    FULFILLMENT_NETWORK_ERROR = 'Fulfillment Network Error'
    FULFILLMENT_TIMEOUT_ERROR = 'Fulfillment Timeout Error'
    FULFILLMENT_SERVER_ERROR = 'Fulfillment Server Error'
    OPEN = 'Open'
