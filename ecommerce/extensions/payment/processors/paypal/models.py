from django.db import models

from fernet_fields import EncryptedCharField

from ecommerce.extensions.payment.models import PaymentProcessorConfiguration


class PaypalConfiguration(PaymentProcessorConfiguration):
    LIVE = 'live'
    SANDBOX = 'sandbox'
    MODE_CHOICES = (
        (LIVE, LIVE),
        (SANDBOX, SANDBOX)
    )
    client_id = models.CharField(max_length=255, null=False, blank=False)
    client_secret = EncryptedCharField(max_length=255, null=False, blank=False)
    mode = models.CharField(max_length=8, choices=MODE_CHOICES, default=SANDBOX)
    retry_attempts = models.IntegerField(default=1)


class PaypalWebProfile(models.Model):
    id = models.CharField(max_length=255, primary_key=True)
    name = models.CharField(max_length=255, unique=True)
