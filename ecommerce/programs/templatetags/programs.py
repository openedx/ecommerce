from django import template

from ecommerce.programs.constants import BENEFIT_PROXY_CLASS_MAP

register = template.Library()


@register.filter
def benefit_type(benefit):
    _type = benefit.type

    if not _type:
        _type = BENEFIT_PROXY_CLASS_MAP[benefit.proxy_class]

    return _type
