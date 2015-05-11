from django.db import models
from django.utils.translation import ugettext_lazy as _
from simple_history.models import HistoricalRecords


class Refund(models.Model):
    """Main refund model, used to represent the state of a refund."""
    order = models.ForeignKey('order.Order', related_name='refund', verbose_name=_('Order'))
    user = models.ForeignKey('user.User', related_name='refunds', verbose_name=_('User'))
    total_credit_excl_tax = models.DecimalField(_('Total Credit (excl. tax)'), decimal_places=2, max_digits=12)
    
    OPEN, DENIED, ERROR, COMPLETE = ('Open', 'Denied', 'Error', 'Complete')
    STATUS_CHOICES = (
        (OPEN, 'Open'),
        (DENIED, 'Denied'),
        (ERROR, 'Error'),
        (COMPLETE, 'Complete'),
    )
    status = models.CharField(_('Status'), max_length=255, choices=STATUS_CHOICES, default=OPEN)

    history = HistoricalRecords()


class RefundLine(models.Model):
    """A refund line, used to represent the state of a single item as part of a larger Refund."""
    refund = models.ForeignKey('refund.Refund', related_name='lines', verbose_name=_('Refund'))
    order_line = models.ForeignKey('order.Line', related_name='refund_lines', verbose_name=_('Order Line'))
    line_credit_excl_tax = models.DecimalField(_('Line Credit (excl. tax)'), decimal_places=2, max_digits=12)
    quantity = models.PositiveIntegerField(_('Quantity'), default=1)

    OPEN, DENIED, REFUND_ERROR, REFUNDED, REVOCATION_ERROR, COMPLETE = (
        'Open', 'Denied', 'Refund Error', 'Refunded', 'Revocation Error', 'Complete'
    )
    STATUS_CHOICES = (
        (OPEN, 'Open'),
        (DENIED, 'Denied'),
        (REFUND_ERROR, 'Refund Error'),
        (REFUNDED, 'Refunded'),
        (REVOCATION_ERROR, 'Revocation Error'),
        (COMPLETE, 'Complete'),
    )
    status = models.CharField(_('Status'), max_length=255, choices=STATUS_CHOICES, default=OPEN)

    history = HistoricalRecords()
