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


class PaymentEvent(AbstractPaymentEvent):
    processor_name = models.CharField(_("Payment Processor"), max_length=32, blank=True, null=True)


class Line(AbstractLine):
    history = HistoricalRecords()


class EnrollmentCode(models.Model):
    date_created = models.DateField(auto_now_add=True)
    vouchers = models.ManyToManyField('voucher.Voucher', blank=True, related_name='enrollment_codes')
    order_line = models.ForeignKey('order.Line', related_name='enrollment_codes')

# If two models with the same name are declared within an app, Django will only use the first one.
# noinspection PyUnresolvedReferences
from oscar.apps.order.models import *  # noqa pylint: disable=wildcard-import,unused-wildcard-import
