from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class PaypalConfig(AppConfig):
    name = 'ecommerce.payment_processors.paypal'
    verbose_name = _('PayPal Payment Processor')
