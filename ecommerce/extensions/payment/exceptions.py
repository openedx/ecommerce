"""Exceptions and error messages used by payment processors."""


from django.utils.translation import ugettext_lazy as _
from oscar.apps.payment.exceptions import GatewayError, PaymentError

PROCESSOR_NOT_FOUND_DEVELOPER_MESSAGE = "Lookup for a payment processor with name [{name}] failed"
PROCESSOR_NOT_FOUND_USER_MESSAGE = _("We don't support the payment option you selected.")


class ProcessorMisconfiguredError(Exception):
    """ Raised when a payment processor has invalid/missing settings. """


class ProcessorNotFoundError(Exception):
    """Raised when a requested payment processor cannot be found."""


class InvalidSignatureError(GatewayError):
    """The signature of the payment processor's response is invalid."""


class InvalidCybersourceDecision(GatewayError):
    """The decision returned by CyberSource was not recognized."""


class DuplicateReferenceNumber(PaymentError):
    """
    CyberSource returned an error response with reason code 104, indicating that
    a duplicate reference number (i.e., order number) was received in a 15 minute period.

    See https://support.cybersource.com/cybskb/index?page=content&id=C156&pmv=print.
    """


class PartialAuthorizationError(PaymentError):
    """The amount authorized by the payment processor differs from the requested amount."""


class PCIViolation(PaymentError):
    """ Raised when a payment request violates PCI compliance.

    If we are raising this exception BAD things are happening, and the service MUST be taken offline IMMEDIATELY!
    """


class InvalidBasketError(PaymentError):
    """ Payment was made for an invalid basket. """


class AuthorizationError(PaymentError):
    """ Authorization was declined. """


class RedundantPaymentNotificationError(PaymentError):
    """ Raised when duplicate payment notification is detected with same transaction ID. """


class ExcessivePaymentForOrderError(PaymentError):
    """ Raised when duplicate payment notification is detected with different transaction ID. """


class SDNFallbackDataEmptyError(Exception):
    """ Error for when we call checkSDNFallback and the data is not yet populated.
    This data is populated by running: ./manage.py populate_sdn_fallback_data_and_metadata
    See ecommerce ADR 0007-sdn-fallback for more info """
