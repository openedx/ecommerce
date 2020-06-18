

from functools import wraps

from django.contrib.auth.views import redirect_to_login
from oscar.core.loading import get_model

from ecommerce.extensions.api import exceptions
from ecommerce.extensions.voucher.utils import get_cached_voucher

Voucher = get_model('voucher', 'Voucher')


def login_required_for_credit(function):
    """
    Decorator for requiring a user to login if offer is for credit seats.
    """
    @wraps(function)
    def decorator(request, *args, **kwargs):
        code = request.GET.get('code', None)
        try:
            voucher = get_cached_voucher(code)
            offer = voucher.best_offer
            if offer.condition.range and offer.condition.range.course_seat_types == 'credit':
                if not request.user.is_authenticated:
                    # The next url needs to have the coupon code as a query parameter.
                    next_url = '{}?{}'.format(request.path, request.META.get('QUERY_STRING'))
                    return redirect_to_login(next_url)
        except (Voucher.DoesNotExist, exceptions.ProductNotFoundError):
            pass
        return function(request, *args, **kwargs)
    return decorator
