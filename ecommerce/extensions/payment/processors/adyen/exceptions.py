from oscar.apps.payment.exceptions import GatewayError


class AdyenRequestError(GatewayError):
    """ Adyen API request returned with a non-200 status code """
    def __init__(self, message, adyen_response):
        self.message = message
        self.adyen_response = adyen_response

    def __str__(self):
        return repr(self.message)


class InvalidAdyenDecision(GatewayError):
    """The decision returned by Adyen was not recognized."""
    pass


class MissingAdyenEventCodeException(GatewayError):
    """The eventCode was not returned by Adyen."""
    pass


class UnsupportedAdyenEventException(GatewayError):
    """The event returned by Adyen was not recognized."""
    pass
