"""Exceptions and error messages used by payment processors."""
from django.utils.translation import ugettext_lazy as _
from oscar.apps.payment.exceptions import GatewayError, PaymentError


PROCESSOR_NOT_FOUND_DEVELOPER_MESSAGE = u"Lookup for a payment processor with name [{name}] failed"
PROCESSOR_NOT_FOUND_USER_MESSAGE = _("We don't support the payment option you selected.")


class ProcessorNotFoundError(Exception):
    """Raised when a requested payment processor cannot be found."""
    pass


class InvalidSignatureError(GatewayError):
    """The signature of the payment processor's response is invalid."""
    pass


class InvalidAdyenDecision(GatewayError):
    """The decision returned by Adyen was not recognized."""
    pass


class InvalidCybersourceDecision(GatewayError):
    """The decision returned by CyberSource was not recognized."""
    pass


class PartialAuthorizationError(PaymentError):
    """The amount authorized by the payment processor differs from the requested amount."""
    pass
