import analytics
from django.dispatch import receiver, Signal

from ecommerce.extensions.analytics.utils import is_segment_configured, parse_tracking_context, log_exceptions


# This signal should be emitted after a refund is completed - payment credited AND fulfillment revoked.
post_refund = Signal(providing_args=["refund"])


@receiver(post_refund, dispatch_uid='tracking.post_refund_callback')
@log_exceptions("Failed to emit tracking event upon refund completion.")
def track_completed_refund(sender, refund=None, **kwargs):  # pylint: disable=unused-argument
    """Emit a tracking event when a refund is completed."""
    if not is_segment_configured():
        return

    user_tracking_id, lms_client_id = parse_tracking_context(refund.user)

    # Ecommerce transaction reversal, performed by emitting an event which is the inverse of an
    # order completion event emitted previously.
    # See: https://support.google.com/analytics/answer/1037443?hl=en
    analytics.track(
        user_tracking_id,
        'Completed Order',
        {
            'orderId': refund.order.number,
            'total': '-{}'.format(refund.total_credit_excl_tax),
            'currency': refund.currency,
            'products': [
                {
                    'id': line.order_line.upc,
                    'sku': line.order_line.partner_sku,
                    'name': line.order_line.product.attr.course_key,
                    'price': str(line.line_credit_excl_tax),
                    'quantity': -1 * line.quantity,
                    'category': line.order_line.product.get_product_class().name,
                } for line in refund.lines.all()
            ],
        },
        context={
            'Google Analytics': {
                'clientId': lms_client_id
            }
        },
    )
