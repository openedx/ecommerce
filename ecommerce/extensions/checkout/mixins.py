from oscar.core.loading import get_model
from oscar.apps.checkout.mixins import OrderPlacementMixin

from ecommerce.extensions.fulfillment.mixins import FulfillmentMixin
from ecommerce.extensions.fulfillment.status import ORDER
from ecommerce.extensions.order.constants import PaymentEventTypeName


Source = get_model('payment', 'Source')
SourceType = get_model('payment', 'SourceType')


class EdxOrderPlacementMixin(OrderPlacementMixin, FulfillmentMixin):
    """Mixin which provides functionality for placing orders.

    Any view class which needs to place an order should use this mixin.
    """
    def handle_payment(self, payment_processor, reference, total):  # pylint: disable=arguments-differ
        """Handle payment processing and record payment sources and events.

        This method is responsible for handling payment and recording the
        payment sources (using the add_payment_source method) and payment
        events (using add_payment_event) so they can be linked to the order
        when it is saved later on.

        In the below, let O represent an order yet to be created.

        Arguments:
            payment_processor (BasePaymentProcessor): The payment processor
                responsible for handling transactions which allow for the
                placement of O.
            reference (unicode): Identifier representing a unique charge in the
                payment processor's system which allows the placement of O.
            total (Price): Represents the amount of money which changed hands in
                order to allow the placement of O.

        Returns:
            None
        """
        # NOTE: If the payment processor in use requires us to explicitly clear
        # authorized transactions (e.g., PayPal), this method should be modified to
        # perform any necessary requests.
        source_type, __ = SourceType.objects.get_or_create(name=payment_processor.NAME)
        source = Source(
            source_type=source_type,
            reference=reference,
            amount_allocated=total.excl_tax
        )
        self.add_payment_source(source)

        # Record payment event
        self.add_payment_event(
            PaymentEventTypeName.PAID,
            total.excl_tax,
            reference=reference
        )

    def handle_successful_order(self, order):
        """Take any actions required after an order has been successfully placed.

        This system is currently designed to sell digital products, so this method
        attempts to immediately fulfill newly-placed orders.
        """
        return self.fulfill_order(order)

    def get_initial_order_status(self, basket):
        """Returns the state in which newly-placed orders are expected to be."""
        return ORDER.OPEN
