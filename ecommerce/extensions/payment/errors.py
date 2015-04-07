"""Exceptions and error messages used by payment processors."""


class PaymentProcessorError(Exception):
    """Standard error raised by payment processors."""
    pass


class CybersourceError(PaymentProcessorError):
    """Standard error thrown by the CyberSource processor implementation."""
    pass


class ExcessiveMerchantDefinedData(CybersourceError):
    """Raised when provided merchant-defined data exceeds CyberSource's optional field limit."""
    pass


class SignatureException(CybersourceError):
    """ The calculated signature does not match the signature we received. """
    pass


class DataException(CybersourceError):
    """The parameters we received from CyberSource were not valid (missing keys, wrong types)"""
    pass


class WrongAmountException(CybersourceError):
    """ The user did not pay the correct amount. """
    pass


class UserCancelled(CybersourceError):
    """ The user cancelled the transaction. """
    pass


class PaymentDeclined(CybersourceError):
    """Payment declined."""
    pass


class UnsupportedProductError(CybersourceError):
    """Cannot generate a receipt for the given product type in this order. """
    pass
