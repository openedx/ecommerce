from django.db import models

from fernet_fields import EncryptedCharField

from ecommerce.extensions.payment.models import PaymentProcessorConfiguration


class AdyenConfiguration(PaymentProcessorConfiguration):
    cse_public_key = models.CharField(max_length=255, null=False, blank=False)
    merchant_account_code = models.CharField(max_length=255, null=False, blank=False)
    payment_api_url = models.CharField(max_length=255, null=False, blank=False)
    notifications_hmac_key = EncryptedCharField(max_length=255, null=False, blank=False)
    web_service_password = EncryptedCharField(max_length=255, null=False, blank=False)
    web_service_username = models.CharField(max_length=255, null=False, blank=False)
