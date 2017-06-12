"""
Decorators related to enterprise functionality.
"""
from functools import wraps

from oscar.core.loading import get_model

from ecommerce.enterprise import utils

Voucher = get_model('voucher', 'Voucher')


def set_enterprise_cookie(func):
    """
    Decorator for applying cookie with enterprise customer uuid.
    """
    @wraps(func)
    def _decorated(request, *args, **kwargs):
        code, enterprise_customer_uuid = request.GET.get('code'), None
        if code:
            enterprise_customer_uuid = utils.get_enterprise_customer_uuid(code)

        response = func(request, *args, **kwargs)

        # Set enterprise customer cookie if enterprise customer uuid is available.
        if enterprise_customer_uuid:
            response = utils.set_enterprise_customer_cookie(request.site, response, enterprise_customer_uuid)

        return response
    return _decorated
