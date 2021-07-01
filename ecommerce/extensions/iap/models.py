from solo.models import SingletonModel

from django.db import models
from django.utils.translation import ugettext_lazy as _


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
