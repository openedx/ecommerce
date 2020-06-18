

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import ugettext_lazy as _
from django_extensions.db.models import TimeStampedModel
from simple_history.models import HistoricalRecords


class Invoice(TimeStampedModel):
    NOT_PAID, PAID = 'Not Paid', 'Paid'
    state_choices = (
        (NOT_PAID, _('Not Paid')),
        (PAID, _('Paid')),
    )
    PREPAID, POSTPAID, BULK_PURCHASE, NA = 'Prepaid', 'Postpaid', 'Bulk purchase', 'Not applicable'
    type_choices = (
        (PREPAID, _('Prepaid')),
        (POSTPAID, _('Postpaid')),
        (BULK_PURCHASE, _('Bulk purchase')),
        (NA, _('Not applicable'))
    )
    PERCENTAGE, FIXED = 'Percentage', 'Fixed'
    discount_type_choices = (
        (PERCENTAGE, _('Percentage')),
        (FIXED, _('Fixed'))
    )
    UPDATEABLE_INVOICE_FIELDS = [
        'invoice_discount_type',
        'invoice_discount_value',
        'invoice_number',
        'invoice_payment_date',
        'invoice_type',
        'tax_deducted_source',
    ]
    basket = models.ForeignKey('basket.Basket', null=True, blank=True, on_delete=models.SET_NULL)
    order = models.ForeignKey('order.Order', null=True, blank=False, on_delete=models.SET_NULL)
    business_client = models.ForeignKey('core.BusinessClient', null=True, blank=False, on_delete=models.SET_NULL)
    state = models.CharField(max_length=255, default=NOT_PAID, choices=state_choices)

    number = models.CharField(max_length=255, null=True, blank=True)
    type = models.CharField(max_length=255, default=PREPAID, choices=type_choices, null=True, blank=True)
    payment_date = models.DateTimeField(null=True, blank=True)
    discount_type = models.CharField(
        max_length=255, default=PERCENTAGE, choices=discount_type_choices, null=True, blank=True
    )
    discount_value = models.PositiveIntegerField(null=True, blank=True)
    tax_deducted_source = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        null=True, blank=True
    )

    history = HistoricalRecords()

    @property
    def total(self):
        """Total amount paid for this Invoice"""
        return self.order.total_incl_tax

    @property
    def client(self):
        """Client for this invoice"""
        return self.business_client
