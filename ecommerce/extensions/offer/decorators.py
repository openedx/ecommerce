

from functools import wraps

import waffle


def check_condition_applicability(switches=None):
    """
    Decorator for checking the applicability of a Condition.

    Applies some global logic for determining the applicability
    of a Condition to a Basket. This decorator expects the wrapped
    function to receive a Condition, ConditionalOffer, and Basket
    as parameters.

    Arguments:
        switches (list): List of waffle switch names which should be enabled for
                         the Condition to be applicable to the Basket.
    """
    def outer_wrapper(func):
        @wraps(func)
        def _decorated(condition, offer, basket):
            if offer.partner != basket.site.siteconfiguration.partner:
                return False

            if basket.is_empty:
                return False

            if basket.total_incl_tax == 0:
                return False

            if switches:
                for switch in switches:
                    if not waffle.switch_is_active(switch):
                        return False

            return func(condition, offer, basket)
        return _decorated
    return outer_wrapper
