from oscar.apps.payment.exceptions import GatewayError


class InvalidCybersourceDecision(GatewayError):
    """The decision returned by CyberSource was not recognized."""
    pass
