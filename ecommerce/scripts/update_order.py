"""This scripts remove the data inconsistency of ECOM-3661."""

import logging

from django.db import transaction
from oscar.core.loading import get_model


BasketLine = get_model('basket', 'Line')
Order = get_model('order', 'Order')
LinePrice = get_model('order', 'LinePrice')
PaymentEventQuantity = get_model('order', 'PaymentEventQuantity')
OrderNote = get_model('order', 'OrderNote')
logger = logging.getLogger(__name__)

ORDER_NUMBER = "Affected Order"


def update_order():
    try:
        order = Order.objects.get(number=ORDER_NUMBER)
    except Order.DoesNotExist:
        logger.error("The order %s does not exist.", ORDER_NUMBER)
        return
    with transaction.atomic():
        order.total_incl_tax = 49
        order.total_excl_tax = 49
        order.save()
        order.lines.update(
            quantity=1,
            line_price_incl_tax=49,
            line_price_excl_tax=49,
            line_price_before_discounts_incl_tax=49,
            line_price_before_discounts_excl_tax=49
        )

        LinePrice.objects.filter(order=order).update(quantity=1)

        PaymentEventQuantity.objects.filter(line__in=order.lines.all()).update(quantity=1)

        # Make sure it does not update the lines whom baskets were deleted.
        if order.basket:
            BasketLine.objects.filter(basket=order.basket).update(quantity=1)

        OrderNote.objects.create(
            order=order, message="Flagged in Feb audit. The user was charged correctly for one seat on cybersource "
                                 "but the order was created for two seats. This was due to some error in basket creation."
                                 "Updating the order amount to sync with the payments. Issue detail in ECOM-3661."
        )
    logger.info("The order %s updated successfully.", ORDER_NUMBER)

logger.info("Updating the order %s.", ORDER_NUMBER)
update_order()
