from django.db import models
from django.utils.translation import ugettext_lazy as _
from oscar.apps.order.abstract_models import AbstractOrder

from ecommerce.extensions.fulfillment.status import ORDER


class Order(AbstractOrder):
    payment_processor = models.CharField(_("Payment Processor"), max_length=32, blank=True)

    @property
    def is_paid(self):
        return self.status in [ORDER.PAID, ORDER.REFUNDED, ORDER.COMPLETE, ORDER.FULFILLMENT_ERROR]

    @property
    def can_retry_fulfillment(self):
        """ Returns a boolean indicating if order is eligible to retry fulfillment. """
        return self.status == ORDER.FULFILLMENT_ERROR

    @classmethod
    def check_order_total(cls, order_num, auth_amount, auth_currency):
        """
        Verify that the auth amount given matches the total price of an order and that the currencies
        are also correct.


        Args:
            order_num (str): order number for the given order
            auth_amount (Decimal): the amount that we would like to verify is correct
            auth_currency (str): the currency of the amount we'd like to verify is correct

        Returns:
            True if the amount and currency matches
            False otherwise

        Raises:
            DoesNotExist: if there is no order that matches the number given

        """
        order = Order.objects.get(number=order_num)
        if order.total_excl_tax == auth_amount and order.currency == auth_currency:
            return True
        else:
            # Set the status to indicate that there was an error.
            order.set_status(ORDER.PAYMENT_ERROR)
            return False


# If two models with the same name are declared within an app, Django will only use the first one.
from oscar.apps.order.models import *  # noqa pylint: disable=wildcard-import,unused-wildcard-import
