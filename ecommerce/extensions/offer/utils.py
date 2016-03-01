"""Offer Utility Methods. """
from decimal import Decimal

from django.utils.translation import ugettext_lazy as _
from oscar.core.loading import get_model
from oscar.templatetags.currency_filters import currency

Benefit = get_model('offer', 'Benefit')


def _remove_exponent_and_trailing_zeros(decimal):
    """
    Remove exponent and trailing zeros.

    Arguments:
        decimal (Decimal): Decimal number that needs to be modified

    Returns:
        decimal (Decimal): Modified decimal number without exponent and trailing zeros.
    """
    return decimal.quantize(Decimal(1)) if decimal == decimal.to_integral() else decimal.normalize()


def format_benefit_value(benefit):
    """
    Format benefit value for display based on the benefit type

    Arguments:
        benefit (Benefit): Benefit to be displayed

    Returns:
        benefit_value (str): String value containing formatted benefit value and type.
    """
    benefit_value = _remove_exponent_and_trailing_zeros(Decimal(str(benefit.value)))
    if benefit.type == Benefit.PERCENTAGE:
        benefit_value = _('{benefit_value}%'.format(benefit_value=benefit_value))
    else:
        benefit_value = _('{benefit_value}'.format(benefit_value=currency(benefit_value)))
    return benefit_value
