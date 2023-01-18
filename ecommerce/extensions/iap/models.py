from django.db import models
from django.utils.translation import ugettext_lazy as _
from solo.models import SingletonModel


class IAPProcessorConfiguration(SingletonModel):
    """
    This is a configuration model for IAP Payment Processor.
    """
    retry_attempts = models.PositiveSmallIntegerField(
        default=0,
        verbose_name=_(
            'Number of times to retry failing IAP client actions (e.g., payment creation, payment execution)'
        )
    )

    class Meta:
        verbose_name = "IAP Processor Configuration"


class PaymentProcessorResponseExtension(models.Model):
    """
    This extends extensions.payments.models.PaymentProcessorResponse
    """
    processor_response = models.OneToOneField('payment.PaymentProcessorResponse', on_delete=models.CASCADE,
                                              related_name='extension')
    original_transaction_id = models.CharField(max_length=255, verbose_name=_('Original Transaction ID'), null=True,
                                               blank=True)
