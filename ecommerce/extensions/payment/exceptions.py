"""Exceptions and error messages used by payment processors."""
from __future__ import unicode_literals

from django.utils.translation import ugettext_lazy as _
from oscar.apps.payment.exceptions import GatewayError, PaymentError

PROCESSOR_NOT_FOUND_DEVELOPER_MESSAGE = "Lookup for a payment processor with name [{name}] failed"
PROCESSOR_NOT_FOUND_USER_MESSAGE = _("We don't support the payment option you selected.")


class ProcessorMisconfiguredError(Exception):
    """ Raised when a payment processor has invalid/missing settings. """
    pass


class ProcessorNotFoundError(Exception):
    """Raised when a requested payment processor cannot be found."""
    pass


class InvalidSignatureError(GatewayError):
    """The signature of the payment processor's response is invalid."""
    pass


class InvalidCybersourceDecision(GatewayError):
    """The decision returned by CyberSource was not recognized."""
    pass


class DuplicateReferenceNumber(PaymentError):
    """
    CyberSource returned an error response with reason code 104, indicating that
    a duplicate reference number (i.e., order number) was received in a 15 minute period.

    See https://support.cybersource.com/cybskb/index?page=content&id=C156&pmv=print.
    """
    pass


class PartialAuthorizationError(PaymentError):
    """The amount authorized by the payment processor differs from the requested amount."""
    pass


class PCIViolation(PaymentError):
    """ Raised when a payment request violates PCI compliance.

    If we are raising this exception BAD things are happening, and the service MUST be taken offline IMMEDIATELY!
    """
    pass


class InvalidBasketError(PaymentError):
    """ Payment was made for an invalid basket. """
    pass
