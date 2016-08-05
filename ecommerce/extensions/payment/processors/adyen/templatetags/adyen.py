from django import template


register = template.Library()


@register.assignment_tag
def get_alternative_payment_methods(payment_processor, basket):
    if hasattr(payment_processor, 'get_alternative_payment_methods'):
        return payment_processor.get_alternative_payment_methods(basket)
