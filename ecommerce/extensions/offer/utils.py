"""Offer Utility Methods. """
from decimal import Decimal

from babel.numbers import format_currency

from django.conf import settings
from django.utils.translation import get_language, to_locale, ugettext_lazy as _
from oscar.core.loading import get_model

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


def get_discount_percentage(discount_value, product_price):
    """
    Get discount percentage of discount value applied to a product price.

    Arguments:
        discount_value (float): Discount value
        product_price (float): Price of a product the discount is used on

    Returns:
        float: Discount percentage
    """
    return discount_value / product_price * 100


def get_discount_value(discount_percentage, product_price):
    """
    Get discount value of discount percentage applied to a product price.

    Arguments:
        discount_percentage (float): Discount percentage
        product_price (float): Price of a product the discount is used on

    Returns:
        float: Discount value
    """
    return discount_percentage * product_price / 100.0


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
        converted_benefit = format_currency(
            Decimal(benefit.value), settings.OSCAR_DEFAULT_CURRENCY, format=u'#,##0.00',
            locale=to_locale(get_language()))
        benefit_value = _('${benefit_value}'.format(benefit_value=converted_benefit))
    return benefit_value
