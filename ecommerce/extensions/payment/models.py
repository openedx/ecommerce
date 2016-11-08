from django.db import models
from django.utils.translation import ugettext_lazy as _
from jsonfield import JSONField
from oscar.apps.payment.abstract_models import AbstractSource
from solo.models import SingletonModel

from ecommerce.extensions.payment.constants import CARD_TYPE_CHOICES


class PaymentProcessorResponse(models.Model):
    """ Auditing model used to save all responses received from payment processors. """

    processor_name = models.CharField(max_length=255, verbose_name=_('Payment Processor'))
    transaction_id = models.CharField(max_length=255, verbose_name=_('Transaction ID'), null=True, blank=True)
    basket = models.ForeignKey('basket.Basket', verbose_name=_('Basket'), null=True, blank=True,
                               on_delete=models.SET_NULL)
    response = JSONField()
    created = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta(object):
        get_latest_by = 'created'
        index_together = ('processor_name', 'transaction_id')
        verbose_name = _('Payment Processor Response')
        verbose_name_plural = _('Payment Processor Responses')


class Source(AbstractSource):
    card_type = models.CharField(max_length=255, choices=CARD_TYPE_CHOICES, null=True, blank=True)


class PaypalWebProfile(models.Model):
    id = models.CharField(max_length=255, primary_key=True)
    name = models.CharField(max_length=255, unique=True)


class PaypalProcessorConfiguration(SingletonModel):
    """ This is a configuration model for PayPal Payment Processor"""
    retry_attempts = models.PositiveSmallIntegerField(
        default=0,
        verbose_name=_(
            'Number of times to retry failing Paypal client actions (e.g., payment creation, payment execution)'
        )
    )

    class Meta(object):
        verbose_name = "Paypal Processor Configuration"


# noinspection PyUnresolvedReferences
from oscar.apps.payment.models import *  # noqa pylint: disable=ungrouped-imports, wildcard-import,unused-wildcard-import,wrong-import-position,wrong-import-order
