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
        response = func(request, *args, **kwargs)

        # Set enterprise customer cookie if enterprise customer uuid is available.
        # The max_age of the cookie is set to a relatively short 60 seconds to
        # maintain the Enterprise context across jumps over to other Open edX
        # services, e.g. LMS, but also to ensure that the Enterprise context
        # does not linger longer than it should.
        code, enterprise_customer_uuid = request.GET.get('code'), None
        if code:
            enterprise_customer_uuid = utils.get_enterprise_customer_uuid(code)
            if enterprise_customer_uuid:
                response = utils.set_enterprise_customer_cookie(
                    request.site,
                    response,
                    enterprise_customer_uuid,
                    max_age=60
                )

        return response
    return _decorated
