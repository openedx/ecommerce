# Note: If future versions of django-oscar include new mixins, they will need to be imported here.
from __future__ import unicode_literals

import abc
import logging

import waffle
from django.db import transaction
from ecommerce_worker.fulfillment.v1.tasks import fulfill_order
from oscar.apps.checkout.mixins import OrderPlacementMixin
from oscar.core.loading import get_class, get_model

from ecommerce.core.models import BusinessClient
from ecommerce.extensions.analytics.utils import audit_log, track_segment_event
from ecommerce.extensions.api import data as data_api
from ecommerce.extensions.basket.constants import EMAIL_OPT_IN_ATTRIBUTE
from ecommerce.extensions.basket.utils import ORGANIZATION_ATTRIBUTE_TYPE
from ecommerce.extensions.checkout.exceptions import BasketNotFreeError
from ecommerce.extensions.customer.utils import Dispatcher
from ecommerce.extensions.order.constants import PaymentEventTypeName
from ecommerce.invoice.models import Invoice

CommunicationEventType = get_model('customer', 'CommunicationEventType')
logger = logging.getLogger(__name__)
Basket = get_model('basket', 'Basket')
BasketAttribute = get_model('basket', 'BasketAttribute')
BasketAttributeType = get_model('basket', 'BasketAttributeType')
Order = get_model('order', 'Order')
post_checkout = get_class('checkout.signals', 'post_checkout')
PaymentEvent = get_model('order', 'PaymentEvent')
PaymentEventType = get_model('order', 'PaymentEventType')
Source = get_model('payment', 'Source')
SourceType = get_model('payment', 'SourceType')


class EdxOrderPlacementMixin(OrderPlacementMixin):
    """ Mixin for edX-specific order placement. """

    # Instance of a payment processor with which to handle payment. Subclasses should set this value.
    payment_processor = None

    duplicate_order_attempt_msg = 'Duplicate Order Attempt: %s payment was received, but an order with number [%s] ' \
                                  'already exists. Basket id: [%d].'
    order_placement_failure_msg = 'Order Failure: %s payment was received, but an order for basket [%d] ' \
                                  'could not be placed.'

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
        handled_processor_response = self.payment_processor.handle_processor_response(response, basket=basket)
        self.record_payment(basket, handled_processor_response)

    def emit_checkout_step_events(self, basket, handled_processor_response, payment_processor):
        """ Emit events necessary to track the user in the checkout funnel. """

        properties = {
            'checkout_id': basket.order_number,
            'step': 1,
            'payment_method': '{} | {}'.format(handled_processor_response.card_type, payment_processor.NAME)
        }
        track_segment_event(basket.site, basket.owner, 'Checkout Step Completed', properties)

        properties['step'] = 2
        track_segment_event(basket.site, basket.owner, 'Checkout Step Viewed', properties)
        track_segment_event(basket.site, basket.owner, 'Checkout Step Completed', properties)

    def record_payment(self, basket, handled_processor_response):
        self.emit_checkout_step_events(basket, handled_processor_response, self.payment_processor)
        track_segment_event(basket.site, basket.owner, 'Payment Info Entered', {'checkout_id': basket.order_number})
        source_type, __ = SourceType.objects.get_or_create(name=self.payment_processor.NAME)
        total = handled_processor_response.total
        reference = handled_processor_response.transaction_id
        source = Source(
            source_type=source_type,
            currency=handled_processor_response.currency,
            amount_allocated=total,
            amount_debited=total,
            reference=reference,
            label=handled_processor_response.card_number,
            card_type=handled_processor_response.card_type
        )
        event_type, __ = PaymentEventType.objects.get_or_create(name=PaymentEventTypeName.PAID)
        payment_event = PaymentEvent(event_type=event_type, amount=total, reference=reference,
                                     processor_name=self.payment_processor.NAME)
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

    def handle_order_placement(self,
                               order_number,
                               user,
                               basket,
                               shipping_address,
                               shipping_method,
                               shipping_charge,
                               billing_address,
                               order_total,
                               request=None,
                               **kwargs):
        """
        Place an order and mark the corresponding basket as submitted.

        Differs from the superclass' method by wrapping order placement
        and basket submission in a transaction. Should be used only in
        the context of an exception handler.
        """
        with transaction.atomic():
            order = self.place_order(
                order_number=order_number,
                user=user,
                basket=basket,
                shipping_address=shipping_address,
                shipping_method=shipping_method,
                shipping_charge=shipping_charge,
                order_total=order_total,
                billing_address=billing_address,
                request=request,
                **kwargs
            )

            basket.submit()

        return self.handle_successful_order(order, request)

    def handle_successful_order(self, order, request=None):  # pylint: disable=arguments-differ
        """Send a signal so that receivers can perform relevant tasks (e.g., fulfill the order)."""
        audit_log(
            'order_placed',
            amount=order.total_excl_tax,
            basket_id=order.basket.id,
            currency=order.currency,
            order_number=order.number,
            user_id=order.user.id,
            contains_coupon=order.contains_coupon
        )

        # Check for the user's email opt in preference, defaulting to false if it hasn't been set
        try:
            email_opt_in = BasketAttribute.objects.get(
                basket=order.basket,
                attribute_type=BasketAttributeType.objects.get(name=EMAIL_OPT_IN_ATTRIBUTE),
            ).value_text == 'True'
        except BasketAttribute.DoesNotExist:
            email_opt_in = False

        if waffle.sample_is_active('async_order_fulfillment'):
            # Always commit transactions before sending tasks depending on state from the current transaction!
            # There's potential for a race condition here if the task starts executing before the active
            # transaction has been committed; the necessary order doesn't exist in the database yet.
            # See http://celery.readthedocs.org/en/latest/userguide/tasks.html#database-transactions.
            fulfill_order.delay(
                order.number,
                site_code=order.site.siteconfiguration.partner.short_code,
                email_opt_in=email_opt_in
            )
        else:
            post_checkout.send(sender=self, order=order, request=request, email_opt_in=email_opt_in)

        return order

    def place_free_order(self, basket, request=None):
        """Fulfill a free order.

        Arguments:
            basket(Basket): the free basket.

        Returns:
            order(Order): the fulfilled order.

        Raises:
            BasketNotFreeError: if the basket is not free.
        """

        if basket.total_incl_tax != 0:
            raise BasketNotFreeError

        basket.freeze()

        order_metadata = data_api.get_order_metadata(basket)

        logger.info(
            'Preparing to place order [%s] for the contents of basket [%d]',
            order_metadata['number'],
            basket.id,
        )

        # Place an order. If order placement succeeds, the order is committed
        # to the database so that it can be fulfilled asynchronously.
        order = self.handle_order_placement(
            basket=basket,
            billing_address=None,
            order_number=order_metadata['number'],
            order_total=order_metadata['total'],
            request=request,
            shipping_address=None,
            shipping_charge=order_metadata['shipping_charge'],
            shipping_method=order_metadata['shipping_method'],
            user=basket.owner
        )

        return order

    def send_confirmation_message(self, order, code, site=None, **kwargs):
        ctx = self.get_message_context(order)
        try:
            event_type = CommunicationEventType.objects.get(code=code)
        except CommunicationEventType.DoesNotExist:
            # No event-type in database, attempt to find templates for this
            # type and render them immediately to get the messages.  Since we
            # have not CommunicationEventType to link to, we can't create a
            # CommunicationEvent instance.
            messages = CommunicationEventType.objects.get_and_render(code, ctx)
            event_type = None
        else:
            messages = event_type.get_messages(ctx)

        if messages and messages['body']:
            logger.info("Order #%s - sending %s messages", order.number, code)
            dispatcher = Dispatcher(logger)
            dispatcher.dispatch_order_messages(order, messages, event_type, site, **kwargs)
        else:
            logger.warning("Order #%s - no %s communication event type",
                           order.number, code)

    def handle_post_order(self, order):
        """
        Handle extra processing of order after its placed.

        This method links the provided order with the BusinessClient for bulk
        purchase through Invoice model.

        Arguments:
            order (Order): Order object

        """
        basket_has_enrollment_code_product = any(
            line.product.is_enrollment_code_product for line in order.basket.all_lines()
        )

        organization_attribute = BasketAttributeType.objects.filter(name=ORGANIZATION_ATTRIBUTE_TYPE).first()
        if not organization_attribute:
            return None

        business_client = BasketAttribute.objects.filter(
            basket=order.basket,
            attribute_type=organization_attribute,
        ).first()
        if basket_has_enrollment_code_product and business_client:
            client, __ = BusinessClient.objects.get_or_create(name=business_client.value_text)
            Invoice.objects.create(
                order=order, business_client=client, type=Invoice.BULK_PURCHASE, state=Invoice.PAID
            )

    def log_order_placement_exception(self, order_number, basket_id):
        payment_processor = self.payment_processor.NAME.title() if self.payment_processor else None
        if Order.objects.filter(number=order_number).exists():
            # One cause of this is Cybersource sending us duplicate notifications for a single payment.
            # See Jira ticket EG-15
            logger.exception(
                self.duplicate_order_attempt_msg, payment_processor, order_number, basket_id
            )
        else:
            logger.exception(self.order_placement_failure_msg, payment_processor, basket_id)
