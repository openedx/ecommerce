from oscar.apps.payment.exceptions import GatewayError


class InvalidAdyenDecision(GatewayError):
    """The decision returned by Adyen was not recognized."""
    pass


class MissingAdyenEventCodeException(GatewayError):
    """The eventCode was not returned by Adyen."""
    pass


class UnsupportedAdyenEventException(GatewayError):
    """The event returned by Adyen was not recognized."""
    pass
