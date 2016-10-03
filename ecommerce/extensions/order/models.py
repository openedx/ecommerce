# noinspection PyUnresolvedReferences
from django.db import models
from django.utils.translation import ugettext_lazy as _
from oscar.apps.order.abstract_models import AbstractOrder, AbstractPaymentEvent, AbstractLine
from simple_history.models import HistoricalRecords

from ecommerce.extensions.fulfillment.status import ORDER


class Order(AbstractOrder):
    history = HistoricalRecords()

    @property
    def is_fulfillable(self):
        """Returns a boolean indicating if order can be fulfilled."""
        return self.status in (ORDER.OPEN, ORDER.FULFILLMENT_ERROR)

    @property
    def contains_coupon(self):
        """ Return a boolean if the order contains a Coupon. """
        return any(line.product.get_product_class().name == 'Coupon' for line in
                   self.basket.all_lines())

    class Meta(object):
        get_latest_by = 'date_placed'


class PaymentEvent(AbstractPaymentEvent):
    processor_name = models.CharField(_("Payment Processor"), max_length=32, blank=True, null=True)


class Line(AbstractLine):
    history = HistoricalRecords()


# If two models with the same name are declared within an app, Django will only use the first one.
# noinspection PyUnresolvedReferences
from oscar.apps.order.models import *  # noqa pylint: disable=wildcard-import,unused-wildcard-import,wrong-import-position,wrong-import-order,ungrouped-imports
