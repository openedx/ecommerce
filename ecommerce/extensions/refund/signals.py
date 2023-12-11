

from django.dispatch import Signal, receiver

from ecommerce.core.constants import SEAT_PRODUCT_CLASS_NAME
from ecommerce.extensions.analytics.utils import silence_exceptions, track_segment_event

# This signal should be emitted after a refund is completed - payment credited AND fulfillment revoked.
post_refund = Signal()


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
        'total': refund.total_credit_excl_tax,
    }
    # The initial version of the refund email only supports refunding a single course.
    first_product = refund.lines.first().order_line.product
    product_class = first_product.get_product_class().name
    if product_class == SEAT_PRODUCT_CLASS_NAME:
        title = first_product.course.name
    else:
        title = first_product.title
    properties['title'] = title

    track_segment_event(refund.order.site, refund.user, 'Order Refunded', properties)
