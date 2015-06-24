# Note: If future versions of django-oscar include new mixins, they will need to be imported here.
import abc

from oscar.apps.checkout.mixins import OrderPlacementMixin
from oscar.core.loading import get_class

from ecommerce.extensions.analytics.utils import audit_log


post_checkout = get_class('checkout.signals', 'post_checkout')


class EdxOrderPlacementMixin(OrderPlacementMixin):
    """ Mixin for edX-specific order placement. """

    # Instance of a payment processor with which to handle payment. Subclasses should set this value.
    payment_processor = None

    __metaclass__ = abc.ABCMeta

    def add_payment_event(self, event):  # pylint: disable = arguments-differ
        """ Record a payment event for creation once the order is placed. """
        if self._payment_events is None:
            self._payment_events = []
        self._payment_events.append(event)

    def handle_payment(self, response, basket):
        """
        Handle any payment processing and record payment sources and events.

        This method is responsible for handling payment and recording the
        payment sources (using the add_payment_source method) and payment
        events (using add_payment_event) so they can be
        linked to the order when it is saved later on.
        """
        source, payment_event = self.payment_processor.handle_processor_response(response, basket=basket)

        self.add_payment_source(source)
        self.add_payment_event(payment_event)

        audit_log(
            'payment_received',
            amount=payment_event.amount,
            basket_id=basket.id,
            currency=source.currency,
            processor_name=payment_event.processor_name,
            reference=payment_event.reference,
            user_id=basket.owner.id
        )

    def handle_successful_order(self, order):
        """Send a signal so that receivers can perform relevant tasks (e.g., fulfill the order)."""
        post_checkout.send_robust(sender=self, order=order)

        audit_log(
            'order_placed',
            amount=order.total_excl_tax,
            basket_id=order.basket.id,
            currency=order.currency,
            order_number=order.number,
            user_id=order.user.id
        )

        return order
