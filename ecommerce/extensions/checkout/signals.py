from functools import wraps
import logging

import analytics
from django.conf import settings
from django.dispatch import receiver
from oscar.core.loading import get_class


post_checkout = get_class('checkout.signals', 'post_checkout')
logger = logging.getLogger(__name__)


def log_exceptions(msg):
    """ Log exceptions (avoiding clutter/indentation).

    Exceptions are still raised; this module assumes that signal receivers are
    being invoked with `send_robust`, or that callers will otherwise mute
    exceptions as needed.
    """
    def decorator(func):  # pylint: disable=missing-docstring
        @wraps(func)
        def wrapper(*a, **kw):  # pylint: disable=missing-docstring
            try:
                return func(*a, **kw)
            except:  # pylint: disable=bare-except
                logger.exception(msg)
                raise
        return wrapper
    return decorator


@receiver(post_checkout, dispatch_uid='tracking.post_checkout_callback')
@log_exceptions("Failed to emit tracking event upon order completion.")
def track_completed_order(sender, order=None, **kwargs):  # pylint: disable=unused-argument
    """
    Fire a tracking event when the order has been placed
    """
    if settings.SEGMENT_KEY is None:
        return

    tracking_context = order.user.tracking_context or {}
    track_user_id = tracking_context.get('lms_user_id')
    if not track_user_id:
        # Even if we cannot extract a good platform user id from the context, we can still track the
        # event with an arbitrary local user id.  However, we need to disambiguate the id we choose
        # since there's no guarantee it won't collide with a platform user id that may be tracked
        # at some point.
        track_user_id = 'ecommerce-{}'.format(order.user.id)

    analytics.track(
        track_user_id,
        'Completed Order',
        {
            'orderId': order.number,
            'total': str(order.total_excl_tax),
            'currency': order.currency,
            'products': [
                {
                    'id': line.upc,
                    'sku': line.partner_sku,
                    'name': line.product.attr.course_key,
                    'price': str(line.line_price_excl_tax),
                    'quantity': line.quantity,
                    'category': line.product.product_class.name,
                } for line in order.lines.all()
            ],
        },
        context={
            'Google Analytics': {
                'clientId': tracking_context.get('lms_client_id')
            }
        },
    )
