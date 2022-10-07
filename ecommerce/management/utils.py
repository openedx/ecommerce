

import logging

from django.db.models import Q
from oscar.apps.partner import strategy
from oscar.core.loading import get_class, get_model

from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.payment.constants import CYBERSOURCE_CARD_TYPE_MAP, STRIPE_CARD_TYPE_MAP
from ecommerce.extensions.payment.helpers import get_processor_class_by_name
from ecommerce.extensions.payment.processors import HandledProcessorResponse

logger = logging.getLogger(__name__)

Applicator = get_class('offer.applicator', 'Applicator')
Basket = get_model('basket', 'Basket')
EventHandler = get_class('order.processing', 'EventHandler')
NoShippingRequired = get_class('shipping.methods', 'NoShippingRequired')
Order = get_model('order', 'Order')
OrderTotalCalculator = get_class('checkout.calculators', 'OrderTotalCalculator')
ShippingEventType = get_model('order', 'ShippingEventType')

SHIPPING_EVENT_NAME = 'Shipped'

_payment_processors = {}


def _get_payment_processor(site, name):
    key = (site, name,)
    payment_processor = _payment_processors.get(key)

    if not payment_processor:
        payment_processor = get_processor_class_by_name(name)(site)
        _payment_processors[key] = payment_processor

    return payment_processor


def refund_basket_transactions(site, basket_ids):
    baskets = Basket.objects.filter(site=site, id__in=basket_ids)

    success_count = 0
    failure_count = 0

    for basket in baskets:
        basket.strategy = strategy.Default()
        Applicator().apply(basket, basket.owner, None)

        logger.info('Refunding transactions for basket [%d]...', basket.id)
        transactions = set(
            list(basket.paymentprocessorresponse_set.values_list('processor_name', 'transaction_id')))

        for processor_name, transaction_id in transactions:
            try:
                logger.info('Issuing credit for [%s] transaction [%s] made against basket [%d]...', processor_name,
                            transaction_id, basket.id)
                payment_processor = _get_payment_processor(site, processor_name)
                payment_processor.issue_credit(basket.order_number, basket, transaction_id, basket.total_excl_tax,
                                               basket.currency)
                success_count += 1
                logger.info('Successfully issued credit for [%s] transaction [%s] made against basket [%d].',
                            processor_name, transaction_id, basket.id)
            except Exception:  # pylint: disable=broad-except
                failure_count += 1
                logger.exception('Failed to issue credit for [%s] transaction [%s] made against basket [%d].',
                                 processor_name, transaction_id, basket.id)
        logger.info('Finished processing refunds for basket [%d].', basket.id)

    msg = 'Finished refunding basket transactions. [{success_count}] transactions were successfully refunded. ' \
          '[{failure_count}] attempts failed.'.format(success_count=success_count, failure_count=failure_count)
    logger.info(msg)

    return success_count, failure_count


class FulfillFrozenBaskets(EdxOrderPlacementMixin):

    @staticmethod
    def get_valid_basket(basket_id):
        """
        Checks if basket id is valid.
        :param basket_id: basket's id
        :return: basket object if valid otherwise None
        """
        # Validate the basket.
        try:
            basket = Basket.objects.get(id=basket_id)
        except Basket.DoesNotExist:
            logger.info('Basket %d does not exist', basket_id)
            return None

        # Make sure basket is Frozen which means payment was done.
        if basket.status != basket.FROZEN:
            return None

        return basket

    @staticmethod
    def get_payment_notification(basket):
        """
        Gets payment notifications for basket. logs in case of no successful
        payment notification or multiple successful payment notifications.
        :return: first successful payment notification or None if no successful
        payment notification exists.
        """
        # Filter the successful payment processor response which in case
        # of Cybersource includes "u'decision': u'ACCEPT'" and in case of
        # Paypal includes "u'state': u'approved'" and in the case of Stripe
        # includes "u'status': u'succeeded'".
        successful_transaction = basket.paymentprocessorresponse_set.filter(
            Q(response__contains='ACCEPT') | Q(response__contains='approved') | Q(response__contains='succeeded')
        )

        # In case of no successful transactions log and return none.
        if not successful_transaction:
            logger.info('Basket %d does not have any successful payment response', basket.id)
            return None

        # Check and log if multiple payment notifications found
        unique_transaction_ids = {response.transaction_id for response in successful_transaction}
        if len(unique_transaction_ids) > 1:
            logger.warning('Basket %d has more than one successful transaction id, using the first one', basket.id)
        return successful_transaction[0]

    @staticmethod
    def get_card_info_from_payment_notification(payment_notification):
        if payment_notification.transaction_id.startswith('PAY'):
            card_number = 'Paypal Account'
            card_type = None
        elif payment_notification.transaction_id.startswith('pi_'):
            card_number = payment_notification.response['payment_method']['card']['last4']
            stripe_card_type = payment_notification.response['payment_method']['card']['brand']
            card_type = STRIPE_CARD_TYPE_MAP[stripe_card_type]
        else:
            card_number = payment_notification.response['req_card_number']
            cybersource_card_type = payment_notification.response['req_card_type']
            card_type = CYBERSOURCE_CARD_TYPE_MAP[cybersource_card_type]
        return (card_number, card_type)

    def fulfill_basket(self, basket_id, site):

        logger.info('Trying to complete order for frozen basket %d', basket_id)

        basket = self.get_valid_basket(basket_id)

        if not basket:
            return False

        # We need to check if an order for basket exists.
        try:
            order = Order.objects.get(basket=basket)
            logger.info('Basket %d does have a existing order %s', basket.id, basket.order_number)
        except Order.DoesNotExist:
            order = None

        # if no order exists we need to create a new order.
        if not order:
            basket.strategy = strategy.Default()

            # Need to handle the case that applied voucher has been expired.
            # This will create the order  with out discount but subsequently
            # run the fulfillment to update course mode.
            try:
                Applicator().apply(basket, user=basket.owner)
            except ValueError:
                basket.clear_vouchers()

            payment_notification = self.get_payment_notification(basket)
            if not payment_notification:
                return False

            try:
                card_number, card_type = self.get_card_info_from_payment_notification(payment_notification)
            except (KeyError, TypeError):
                logger.exception('Unable to parse payment details for basket %d', basket.id)
                return False

            self.payment_processor = _get_payment_processor(site, payment_notification.processor_name)
            # Create handled response
            handled_response = HandledProcessorResponse(
                transaction_id=payment_notification.transaction_id,
                total=basket.total_excl_tax,
                currency=basket.currency,
                card_number=card_number,
                card_type=card_type
            )

            # Record Payment and try to place order
            try:
                self.record_payment(basket=basket, handled_processor_response=handled_response)

                shipping_method = NoShippingRequired()
                shipping_charge = shipping_method.calculate(basket)
                order_total = OrderTotalCalculator().calculate(basket, shipping_charge)

                user = basket.owner
                # Given a basket, order number generation is idempotent. Although we've already
                # generated this order number once before, it's faster to generate it again
                # than to retrieve an invoice number from PayPal.
                order_number = basket.order_number

                self.handle_order_placement(
                    order_number=order_number,
                    user=user,
                    basket=basket,
                    shipping_address=None,
                    shipping_method=shipping_method,
                    shipping_charge=shipping_charge,
                    billing_address=None,
                    order_total=order_total,
                )
                logger.info('Successfully created order for basket %d', basket.id)
                return True
            except:  # pylint: disable=bare-except
                logger.exception('Unable to create order for basket %d', basket.id)
                return False

        # Start order fulfillment if order exists but is not fulfilled.
        elif order.is_fulfillable:
            order_lines = order.lines.all()
            line_quantities = [line.quantity for line in order_lines]

            shipping_event, __ = ShippingEventType.objects.get_or_create(name=SHIPPING_EVENT_NAME)
            EventHandler().handle_shipping_event(order, shipping_event, order_lines, line_quantities)

            if order.is_fulfillable:
                logger.error('Unable to fulfill order for basket %d', basket.id)
                return False
        return True
