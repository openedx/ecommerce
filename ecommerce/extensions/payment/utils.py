from math import pow

from django.conf import settings
from django.utils.translation import ugettext_lazy as _


def middle_truncate(string, chars):
    """Truncate the provided string, if necessary.

    Cuts excess characters from the middle of the string and replaces
    them with a string indicating that truncation has occurred.

    Arguments:
        string (unicode or str): The string to be truncated.
        chars (int): The character limit for the truncated string.

    Returns:
        Unicode: The truncated string, of length less than or equal to `chars`.
            If no truncation was required, the original string is returned.

    Raises:
        ValueError: If the provided character limit is less than the length of
            the truncation indicator.
    """
    if len(string) <= chars:
        return string

    # Translators: This is a string placed in the middle of a truncated string
    # to indicate that truncation has occurred. For example, if a title may only
    # be at most 11 characters long, "A Very Long Title" (17 characters) would be
    # truncated to "A Ve...itle".
    indicator = _('...')

    indicator_length = len(indicator)
    if chars < indicator_length:
        raise ValueError

    slice_size = (chars - indicator_length) / 2
    start, end = string[:slice_size], string[-slice_size:]
    truncated = u'{start}{indicator}{end}'.format(start=start, indicator=indicator, end=end)

    return truncated


def minor_units(price, currency_code):
    """
    Calculates the number of minor units given the major unit price for the given currency code.

    Some currencies do not have decimal points, such as JPY, and some have 3 decimal points, such as BHD.
    For example, 10 GBP is submitted as 1000, whereas 10 JPY is submitted as 10.

    Arguments:
        price (Decimal): The major unit price to be converted.
        currency_code (str): The currency code.

    Returns:
        int: The number of minor units.

    Raises:
        KeyError: If the given currency code has not been configured in application settings,
    """
    return int(round(float(price) * pow(10, settings.CURRENCY_CODES[currency_code]['exponent'])))
