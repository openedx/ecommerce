"""Mixins to support views that fulfill orders."""
from oscar.core.loading import get_model, get_class


ShippingEventType = get_model('order', 'ShippingEventType')

EventHandler = get_class('order.processing', 'EventHandler')


class FulfillmentMixin(object):
    """A mixin that provides the ability to fulfill orders."""
    SHIPPING_EVENT_NAME = 'Shipped'

    def fulfill_order(self, order):
        """Attempt fulfillment of an order."""
        order_lines = order.lines.all()
        line_quantities = [line.quantity for line in order_lines]

        shipping_event = ShippingEventType.objects.get(name=self.SHIPPING_EVENT_NAME)
        fulfilled_order = EventHandler().handle_shipping_event(order, shipping_event, order_lines, line_quantities)
        return fulfilled_order
