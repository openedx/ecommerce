""" Override the default order processing in Django Oscar.

This is the entry point from Django Oscar for fulfillment of completed Orders. handle_shipping_event is
overridden to use our custom fulfillment API.  Orders will either be fulfilled, or updated with the appropriate
errors explaining why fulfillment may fail.

"""
from oscar.apps.order import exceptions, processing

from ecommerce.extensions.fulfillment import api as fulfillment_api
from ecommerce.extensions.fulfillment.status import LINE


class EventHandler(processing.EventHandler):
    """ Handles Order Processing

    An override from Django Oscar for processing orders through the Fulfillment API.

    """

    def handle_shipping_event(self, order, event_type, lines, line_quantities, **kwargs):
        self.validate_shipping_event(order, event_type, lines, line_quantities, **kwargs)

        email_opt_in = kwargs.get('email_opt_in', False)
        order = fulfillment_api.fulfill_order(order, lines, email_opt_in=email_opt_in)

        self.create_shipping_event(order, event_type, lines, line_quantities, **kwargs)

        return order

    def create_shipping_event(self, order, event_type, lines, line_quantities, **kwargs):
        """
        Creates a ShippingEvent for the order.

        The ShippingEvent will only contain related LineQuantity objects for items that have been successfully
        fulfilled/shipped (e.g. status is Complete). If no items have been fulfilled, the value None will be returned.
        """
        reference = kwargs.get('reference', '')
        event = order.shipping_events.create(event_type=event_type, notes=reference)
        event_has_lines = False

        try:
            for line, quantity in zip(lines, line_quantities):
                # The line should only be added to the ShippingEvent if the line is complete and was
                # not previously shipped.
                if line.status == LINE.COMPLETE and not line.has_shipping_event_occurred(event_type):
                    event.line_quantities.create(line=line, quantity=quantity)
                    event_has_lines = True
        except exceptions.InvalidShippingEvent:  # pragma: no cover
            # CCB: It is practically impossible to mock event.line_quantities.create() and force an error. If the
            # implementation changes in the future, please remove the pragma and test this branch.
            event.delete()
            raise

        if not event_has_lines:
            event.delete()
            return None

        return event
