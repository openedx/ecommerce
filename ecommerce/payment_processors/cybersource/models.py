from django.db import models

from fernet_fields import EncryptedCharField

from ecommerce.extensions.payment.models import PaymentProcessorConfiguration


class CybersourceConfiguration(PaymentProcessorConfiguration):
    access_key = models.CharField(max_length=255, null=False, blank=False)
    merchant_id = models.CharField(max_length=255, null=False, blank=False)
    payment_page_url = models.CharField(max_length=255, null=False, blank=False)
    profile_id = models.CharField(max_length=255, null=False, blank=False)
    secret_key = EncryptedCharField(max_length=255, null=False, blank=False)
    send_level_2_3_details = models.BooleanField(default=True)
    soap_api_url = models.CharField(max_length=255, null=False, blank=False)
    transaction_key = EncryptedCharField(max_length=255, null=False, blank=False)
