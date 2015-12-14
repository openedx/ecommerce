from django_extensions.db.models import TimeStampedModel
from django.db import models
from django.utils.translation import ugettext_lazy as _
from simple_history.models import HistoricalRecords


class Invoice(TimeStampedModel):
    NOT_PAID, PAID = 'Not Paid', 'Paid'
    state_choices = (
        (NOT_PAID, _('Not Paid')),
        (PAID, _('Paid')),
    )
    basket = models.ForeignKey('basket.Basket', null=False, blank=False)
    state = models.CharField(max_length=255, default=NOT_PAID, choices=state_choices)

    history = HistoricalRecords()

    class Meta(TimeStampedModel.Meta):
        index_together = ["modified", "created"]

    def __str__(self):
        return 'Invoice {id} for order number {order}'.format(id=self.id, order=self.basket.order.number)

    @property
    def total(self):
        """Total amount paid for this Invoice"""
        return self.basket.order.total_incl_tax

    @property
    def client(self):
        """Client for this invoice"""
        return self.basket.order.user
