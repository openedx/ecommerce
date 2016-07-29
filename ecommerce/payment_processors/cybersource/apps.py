from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class CybersourceConfig(AppConfig):
    name = 'ecommerce.payment_processors.cybersource'
    verbose_name = _('Cybersource Payment Processor')
