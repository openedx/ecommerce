

from django import template

from ecommerce.extensions.offer.utils import format_benefit_value, get_benefit_type

register = template.Library()


@register.filter(name='benefit_discount')
def benefit_discount(benefit):
    """
    Format benefit value for display based on the benefit type.

    Example:
        '100%' if benefit.value == 100.00 and benefit.type == 'Percentage'
        '$100.00' if benefit.value == 100.00 and benefit.type == 'Absolute'

    Arguments:
        benefit (Benefit): Voucher's Benefit.

    Returns:
        str: String value containing formatted benefit value and type.
    """
    return format_benefit_value(benefit)


@register.filter(name='benefit_type')
def benefit_type(benefit):
    return get_benefit_type(benefit)
