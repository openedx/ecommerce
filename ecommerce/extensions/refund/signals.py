from django.dispatch import receiver, Signal

from ecommerce.courses.utils import mode_for_seat
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

    # Ecommerce transaction reversal, performed by emitting an event which is the inverse of an
    # order completion event emitted previously.
    # See: https://support.google.com/analytics/answer/1037443?hl=en
    refund.order.site.siteconfiguration.track_analytics_event(
        user_tracking_id,
        'Completed Order',
        {
            'orderId': refund.order.number,
            'total': '-{}'.format(refund.total_credit_excl_tax),
            'currency': refund.currency,
            'products': [
                {
                    # For backwards-compatibility with older events the `sku` field is (ab)used to
                    # store the product's `certificate_type`, while the `id` field holds the product's
                    # SKU. Marketing is aware that this approach will not scale once we start selling
                    # products other than courses, and will need to change in the future.
                    'id': line.order_line.partner_sku,
                    'sku': mode_for_seat(line.order_line.product),
                    'name': line.order_line.product.course.id,
                    'price': str(line.line_credit_excl_tax),
                    'quantity': -1 * line.quantity,
                    'category': line.order_line.product.get_product_class().name,
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
