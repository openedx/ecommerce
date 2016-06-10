from django_extensions.db.models import TimeStampedModel
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import ugettext_lazy as _
from simple_history.models import HistoricalRecords


class Invoice(TimeStampedModel):
    NOT_PAID, PAID = 'Not Paid', 'Paid'
    state_choices = (
        (NOT_PAID, _('Not Paid')),
        (PAID, _('Paid')),
    )
    PREPAID, POSTPAID = 'Prepaid', 'Postpaid'
    type_choices = (
        (PREPAID, _('Prepaid')),
        (POSTPAID, _('Postpaid')),
    )
    basket = models.ForeignKey('basket.Basket', null=True, blank=True)
    order = models.ForeignKey('order.Order', null=True, blank=False)
    business_client = models.ForeignKey('core.BusinessClient', null=True, blank=False)
    state = models.CharField(max_length=255, default=NOT_PAID, choices=state_choices)

    history = HistoricalRecords()

    invoice_type = models.CharField(max_length=255, default=PREPAID, choices=type_choices, blank=True, null=True)
    number = models.CharField(max_length=255, blank=True, null=True)
    invoiced_amount = models.PositiveIntegerField(blank=True, null=True)
    invoice_payment_date = models.DateTimeField(blank=True, null=True)
    invoice_discount_type = models.CharField(max_length=255, blank=True, null=True)
    invoice_discount_value = models.PositiveIntegerField(blank=True, null=True)
    tax_deducted_source = models.BooleanField(default=False)
    tax_deducted_source_value = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        blank=True, null=True
    )

    @property
    def total(self):
        """Total amount paid for this Invoice"""
        return self.order.total_incl_tax

    @property
    def client(self):
        """Client for this invoice"""
        return self.business_client
