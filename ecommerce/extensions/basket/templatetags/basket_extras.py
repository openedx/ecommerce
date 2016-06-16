from django import template

from ecommerce.extensions.offer.utils import format_benefit_value


register = template.Library()


@register.assignment_tag
def get_formatted_benefit_value(benefit):
    """
    Format benefit value for display based on the benefit type

    Arguments:
        benefit (Benefit): Benefit to be displayed

    Returns:
        benefit_value (str): String value containing formatted benefit value and type.
    """
    return format_benefit_value(benefit)

