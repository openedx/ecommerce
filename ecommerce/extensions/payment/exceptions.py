"""Exceptions and error messages used by or related to payment processors."""
from django.utils.translation import ugettext_lazy as _


PROCESSOR_NOT_FOUND_DEVELOPER_MESSAGE = u"Lookup for a payment processor with name [{name}] failed"
PROCESSOR_NOT_FOUND_USER_MESSAGE = _("We don't support the payment option you selected.")


class ProcessorNotFoundError(Exception):
    """Raised when a requested payment processor cannot be found."""
    pass
