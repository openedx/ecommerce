from django.dispatch import Signal, receiver

from ecommerce.extensions.analytics.utils import is_segment_configured, parse_tracking_context, silence_exceptions

# This signal should be emitted after a refund is completed - payment credited AND fulfillment revoked.
post_refund = Signal(providing_args=["refund"])


@receiver(post_refund, dispatch_uid='tracking.post_refund_callback')
@silence_exceptions("Failed to emit tracking event upon refund completion.")
def track_completed_refund(sender, refund=None, **kwargs):  # pylint: disable=unused-argument
    """Emit a tracking event when a refund is completed."""
    if not (is_segment_configured() and refund.total_credit_excl_tax > 0):
        return

    user_tracking_id, lms_client_id, lms_ip = parse_tracking_context(refund.user)

    refund.order.site.siteconfiguration.segment_client.track(
        user_tracking_id,
        'Order Refunded',
        {
            'orderId': refund.order.number,
            'products': [
                {
                    'id': line.order_line.partner_sku,
                    'quantity': line.quantity,
                } for line in refund.lines.all()
            ],
        },
        context={
            'ip': lms_ip,
            'Google Analytics': {
                'clientId': lms_client_id
            }
        },
    )
