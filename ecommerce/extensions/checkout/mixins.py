# Note: If future versions of django-oscar include new mixins, they will need to be imported here.
import abc
import logging

import analytics
from django.conf import settings
from oscar.apps.checkout.mixins import OrderPlacementMixin
from oscar.core.loading import get_class


post_checkout = get_class('checkout.signals', 'post_checkout')

logger = logging.getLogger(__name__)


class EdxOrderPlacementMixin(OrderPlacementMixin):
    """ Mixin for edX-specific order placement. """
    _payment_sources = []
    _payment_events = []

    # Note: Subclasses should set this value
    payment_processor = None

    __metaclass__ = abc.ABCMeta

    def add_payment_event(self, event):  # pylint: disable = arguments-differ
        """ Record a payment event for creation once the order is placed. """
        self._payment_events.append(event)

    def handle_payment(self, response, basket):
        """
        Handle any payment processing and record payment sources and events.

        This method is responsible for handling payment and recording the
        payment sources (using the add_payment_source method) and payment
        events (using add_payment_event) so they can be
        linked to the order when it is saved later on.
        """
        source, payment_event, tracking_context = self.payment_processor.handle_processor_response(response,
                                                                                                   basket=basket)
        self.add_payment_source(source)
        self.add_payment_event(payment_event)
        return tracking_context

    def handle_successful_order(self, order):
        # Send a signal so that receivers can perform relevant tasks (e.g. fulfill the order).
        post_checkout.send(sender=self, order=order)
        return order

    def handle_order_placement(self, order_number, user, basket,
                               shipping_address, shipping_method,
                               shipping_charge, billing_address, order_total,
                               tracking_context, **kwargs):  # pylint: disable = arguments-differ
        """
        Overrides the default OrderPlacementMixin behavior to add handling of the tracking_context.
        """
        order = super(EdxOrderPlacementMixin, self).handle_order_placement(order_number, user, basket, shipping_address,
                                                                           shipping_method, shipping_charge,
                                                                           billing_address, order_total, **kwargs)
        try:
            self._track_completed_order(order, user, tracking_context)
        except:  # pylint: disable=bare-except
            # Never block on a problem here.
            logger.warning("Unable to emit tracking event upon order placement, skipping.", exc_info=True)

        return order

    def _track_completed_order(self, order, user, tracking_context):
        """
        Fire a tracking event when the order has been placed
        """
        if settings.SEGMENT_KEY is None:
            return

        track_user_id = tracking_context.get('lms_user_id')
        if not track_user_id:
            # Even if we cannot extract a good platform user id from the context, we can still track the
            # event with an arbitrary local user id.  However, we need to disambiguate the id we choose
            # since there's no guarantee it won't collide with a platform user id that may be tracked
            # at some point.
            track_user_id = 'ecommerce-{}'.format(user.id)

        analytics.track(
            track_user_id,
            'Completed Order',
            {
                'orderId': order.number,
                'total': str(order.total_excl_tax),
                'currency': order.currency,
                'products': [
                    {
                        'id': line.upc,  # NOTE lms shoppingcart reports database id for this, which seems meaningless
                        'sku': line.partner_sku,
                        'name': line.partner_name,  # NOTE lms shoppingcart reports unicode(course_key) here
                        'price': str(line.line_price_excl_tax),
                        'quantity': line.quantity,
                        'category': line.category,  # NOTE lms shoppingcart reports course_key.org here
                    } for line in order.lines.all()
                ],
            },
            context={
                'Google Analytics': {
                    'clientId': tracking_context.get('lms_client_id')
                }
            },
        )
