from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class AdyenConfig(AppConfig):
    name = 'ecommerce.payment_processors.adyen'
    verbose_name = _('Adyen Payment Processor')
