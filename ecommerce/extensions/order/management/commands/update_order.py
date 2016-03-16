"""This scripts remove the data inconsistency of ECOM-3661."""

import logging

from django.core.management import BaseCommand, CommandError
from django.db import transaction
from oscar.core.loading import get_model

BasketLine = get_model('basket', 'Line')
Order = get_model('order', 'Order')
LinePrice = get_model('order', 'LinePrice')
PaymentEventQuantity = get_model('order', 'PaymentEventQuantity')
OrderNote = get_model('order', 'OrderNote')
logger = logging.getLogger(__name__)

ORDER_NUMBER = "EDX-5266181"
AMOUNT = 49.0


class Command(BaseCommand):
    help = 'Update the order flagged in ECOM-3661.'

    def handle(self, *args, **options):
        logger.info("Updating the order [%s] with new amount [%s].", ORDER_NUMBER, AMOUNT)
        try:
            order = Order.objects.get(number=ORDER_NUMBER)
        except Order.DoesNotExist:
            logger.error("The order [%s] does not exist.", ORDER_NUMBER)
            raise CommandError("The order {} does not exist.".format(ORDER_NUMBER))
        with transaction.atomic():
            order.total_incl_tax = AMOUNT
            order.total_excl_tax = AMOUNT
            order.save()
            order.lines.update(
                quantity=1,
                line_price_incl_tax=AMOUNT,
                line_price_excl_tax=AMOUNT,
                line_price_before_discounts_incl_tax=AMOUNT,
                line_price_before_discounts_excl_tax=AMOUNT
            )

            LinePrice.objects.filter(order=order).update(quantity=1)

            PaymentEventQuantity.objects.filter(line__in=order.lines.all()).update(quantity=1)

            # Make sure it does not update the lines whom baskets were deleted.
            if order.basket:
                BasketLine.objects.filter(basket=order.basket).update(quantity=1)

            OrderNote.objects.create(
                order=order, message="Flagged in Feb audit. The user was charged correctly for one seat on cybersource "
                                     "but the order was created for two seats. This was due to some error in basket "
                                     "creation. Updating the order amount to sync with the payments. "
                                     "Issue detail in ECOM-3661."
            )
        logger.info("The order %s updated successfully.", ORDER_NUMBER)
