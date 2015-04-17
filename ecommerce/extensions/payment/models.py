from django.db import models
from django.utils.translation import ugettext_lazy as _
from jsonfield import JSONField


class PaymentProcessorResponse(models.Model):
    """ Auditing model used to save all responses received from payment processors. """

    processor_name = models.CharField(max_length=255, verbose_name=_('Payment Processor'))
    transaction_id = models.CharField(max_length=255, verbose_name=_('Transaction ID'), null=True, blank=True)
    basket = models.ForeignKey('basket.Basket', verbose_name=_('Basket'), null=True, blank=True,
                               on_delete=models.SET_NULL)
    response = JSONField()
    created = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta(object):
        index_together = ('processor_name', 'transaction_id')
        verbose_name = _('Payment Processor Response')
        verbose_name_plural = _('Payment Processor Responses')

# noinspection PyUnresolvedReferences
from oscar.apps.payment.models import *  # noqa pylint: disable=wildcard-import,unused-wildcard-import
