

from django import template

from ecommerce.enterprise import utils
from ecommerce.enterprise.exceptions import EnterpriseDoesNotExist

register = template.Library()


@register.simple_tag(takes_context=True)
def enterprise_customer_for_voucher(context, voucher):
    """
    Retrieve enterprise customer associated with the given voucher.

    Raises:
        EnterpriseDoesNotExist: Voucher is not associated with any enterprise customer.
    """
    if voucher and context and 'request' in context:
        request = context['request']
    else:
        return None

    try:
        return utils.get_enterprise_customer_from_voucher(request.site, voucher)
    except EnterpriseDoesNotExist:
        return None
