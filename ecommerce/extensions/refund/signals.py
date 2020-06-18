

from django.dispatch import Signal, receiver

from ecommerce.extensions.analytics.utils import silence_exceptions, track_segment_event

# This signal should be emitted after a refund is completed - payment credited AND fulfillment revoked.
post_refund = Signal(providing_args=['refund'])


@receiver(post_refund, dispatch_uid='tracking.post_refund_callback')
@silence_exceptions('Failed to emit tracking event upon refund completion.')
def track_completed_refund(sender, refund=None, **kwargs):  # pylint: disable=unused-argument
    """Emit a tracking event when a refund is completed."""
    if refund.total_credit_excl_tax <= 0:
        return

    properties = {
        'orderId': refund.order.number,
        'products': [
            {
                'id': line.order_line.partner_sku,
                'quantity': line.quantity,
            } for line in refund.lines.all()
        ],
    }
    track_segment_event(refund.order.site, refund.user, 'Order Refunded', properties)
