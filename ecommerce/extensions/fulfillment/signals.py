

from django.dispatch import receiver
from oscar.core.loading import get_class, get_model

ShippingEventType = get_model('order', 'ShippingEventType')
EventHandler = get_class('order.processing', 'EventHandler')
post_checkout = get_class('checkout.signals', 'post_checkout')
SHIPPING_EVENT_NAME = 'Shipped'


@receiver(post_checkout, dispatch_uid='fulfillment.post_checkout_callback')
def post_checkout_callback(sender, order=None, **kwargs):  # pylint: disable=unused-argument
    order_lines = order.lines.all()
    line_quantities = [line.quantity for line in order_lines]

    shipping_event, __ = ShippingEventType.objects.get_or_create(name=SHIPPING_EVENT_NAME)
    EventHandler().handle_shipping_event(order, shipping_event, order_lines, line_quantities, **kwargs)
