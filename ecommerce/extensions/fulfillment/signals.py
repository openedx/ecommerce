from django.dispatch import receiver
from oscar.core.loading import get_class, get_model

ShippingEventType = get_model('order', 'ShippingEventType')
EventHandler = get_class('order.processing', 'EventHandler')
post_checkout = get_class('checkout.signals', 'post_checkout')
SHIPPING_EVENT_NAME = 'Shipped'


@receiver(post_checkout, dispatch_uid='fulfillment.post_checkout_callback')
def post_checkout_callback(sender, order=None, **kwargs):  # pylint: disable=unused-argument
    # Note (CCB): This is a minor hack to appease coverage. Since this file is loaded before coverage, the imported
    # module will also be loaded before coverage. Module loaded after coverage are falsely listed as not covered.
    # We do not want the false report, and we do not want to omit the api module from coverage reports. This is the
    # "happy" medium.

    order_lines = order.lines.all()
    line_quantities = [line.quantity for line in order_lines]

    shipping_event, __ = ShippingEventType.objects.get_or_create(name=SHIPPING_EVENT_NAME)
    EventHandler().handle_shipping_event(order, shipping_event, order_lines, line_quantities)
