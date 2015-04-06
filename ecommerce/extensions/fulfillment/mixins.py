""" Mixins to support views that fulfill orders. """

from oscar.core.loading import get_class

from ecommerce.extensions.api import data


EventHandler = get_class('order.processing', 'EventHandler')


class FulfillmentMixin(object):
    """ A mixin that provides the ability to fulfill orders. """
    SHIPPING_EVENT_NAME = 'Shipped'

    def _fulfill_order(self, order):
        """Attempt fulfillment for an order."""
        order_lines = order.lines.all()
        line_quantities = [line.quantity for line in order_lines]

        shipping_event = data.get_shipping_event_type(self.SHIPPING_EVENT_NAME)
        fulfilled_order = EventHandler().handle_shipping_event(order, shipping_event, order_lines, line_quantities)
        return fulfilled_order
