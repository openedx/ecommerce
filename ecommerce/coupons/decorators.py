from functools import wraps

from django.contrib.auth.views import redirect_to_login
from oscar.core.loading import get_model

from ecommerce.extensions.api import exceptions
from ecommerce.extensions.voucher.utils import get_voucher_and_products_from_code

Voucher = get_model('voucher', 'Voucher')


def login_required_for_credit(function):
    """
    Decorator for requiring a user to login if offer is for credit seats.
    """
    @wraps(function)
    def decorator(request, *args, **kwargs):
        code = request.GET.get('code', None)
        try:
            __, products = get_voucher_and_products_from_code(code=code)
            if products[0].attr.certificate_type == 'credit':
                if not request.user.is_authenticated():
                    params = request.META.get('QUERY_STRING')
                    # The next url needs to have the coupon code as a query parameter.
                    next_url = '{}?{}'.format(request.path, params)
                    return redirect_to_login(next_url)
        except (Voucher.DoesNotExist, exceptions.ProductNotFoundError):
            pass
        return function(request, *args, **kwargs)
    return decorator
