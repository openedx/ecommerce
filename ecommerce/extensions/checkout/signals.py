import analytics
from django.dispatch import receiver
from oscar.core.loading import get_class

from ecommerce.extensions.analytics.utils import is_segment_configured, parse_tracking_context, log_exceptions


post_checkout = get_class('checkout.signals', 'post_checkout')


@receiver(post_checkout, dispatch_uid='tracking.post_checkout_callback')
@log_exceptions("Failed to emit tracking event upon order completion.")
def track_completed_order(sender, order=None, **kwargs):  # pylint: disable=unused-argument
    """Emit a tracking event when an order is placed."""
    if not (is_segment_configured() and order.total_excl_tax > 0):
        return

    user_tracking_id, lms_client_id = parse_tracking_context(order.user)

    analytics.track(
        user_tracking_id,
        'Completed Order',
        {
            'orderId': order.number,
            'total': str(order.total_excl_tax),
            'currency': order.currency,
            'products': [
                {
                    # For backwards-compatibility with older events the `sku` field is (ab)used to
                    # store the product's `certificate_type`, while the `id` field holds the product's
                    # SKU. Marketing is aware that this approach will not scale once we start selling
                    # products other than courses, and will need to change in the future.
                    'id': line.partner_sku,
                    'sku': line.product.attr.certificate_type,
                    'name': line.product.title,
                    'price': str(line.line_price_excl_tax),
                    'quantity': line.quantity,
                    'category': line.product.get_product_class().name,
                } for line in order.lines.all()
            ],
        },
        context={
            'Google Analytics': {
                'clientId': lms_client_id
            }
        },
    )
