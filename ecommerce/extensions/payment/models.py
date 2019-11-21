from __future__ import absolute_import, unicode_literals

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _
from django_extensions.db.models import TimeStampedModel
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


@python_2_unicode_compatible
class SDNCheckFailure(TimeStampedModel):
    """ Record of SDN check failure. """
    full_name = models.CharField(max_length=255)
    username = models.CharField(max_length=255)
    city = models.CharField(max_length=32, default='')
    country = models.CharField(max_length=2)
    site = models.ForeignKey('sites.Site', verbose_name=_('Site'), null=True, blank=True, on_delete=models.SET_NULL)
    products = models.ManyToManyField('catalogue.Product', related_name='sdn_failures')
    sdn_check_response = JSONField()

    def __str__(self):
        return 'SDN check failure [{username}]'.format(
            username=self.username
        )

    class Meta(object):
        verbose_name = 'SDN Check Failure'


class EnterpriseContractMetadata(TimeStampedModel):
    """ Record of contract details for a particular customer transaction """
    PERCENTAGE = 'Percentage'
    FIXED = 'Absolute'
    DISCOUNT_TYPE_CHOICES = [
        (PERCENTAGE, _('Percentage')),
        (FIXED, _('Absolute')), 
    ]
    amount_paid = models.DecimalField(null=True, decimal_places=2, max_digits=12)
    discount_value = models.DecimalField(null=True, decimal_places=5, max_digits=15)
    discount_type = models.CharField(max_length=255, choices=DISCOUNT_TYPE_CHOICES, default=PERCENTAGE)

    def clean(self):
        """
        discount_value can hold two types of things conceptually: percentages
        and fixed amounts. We want to add extra validation here on top of the
        normal field validation DecimalField gives us.
        """
        super(EnterpriseContractMetadata, self).clean()

        if self.discount_value is not None:
            if self.discount_type == self.FIXED:
                self._validate_fixed_value()
            else:
                self._validate_percentage_value()


    def _validate_fixed_value(self):
        before_decimal, __, after_decimal = str(self.discount_value).partition('.')

        if len(before_decimal) > 10:
            raise ValidationError(_(
                "More than 10 digits before the decimal "
                "not allowed for fixed value."
            ))

        if len(after_decimal) > 2:
            raise ValidationError(_(
                "More than 2 digits after the decimal "
                "not allowed for fixed value."
            ))

    def _validate_percentage_value(self):

        if Decimal(self.discount_value) > Decimal('100.00000'):
            raise ValidationError(_(
                "Percentage greater than 100 not allowed."
            ))


# noinspection PyUnresolvedReferences
from oscar.apps.payment.models import *  # noqa isort:skip pylint: disable=ungrouped-imports, wildcard-import,unused-wildcard-import,wrong-import-position,wrong-import-order
