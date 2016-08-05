from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class InvoicePaymentConfig(AppConfig):
    name = 'ecommerce.extensions.payment.processors.invoice_payment'
    verbose_name = _('Invoice Payment Processor')

    def ready(self):
        # Import the processor class on startup so that
        # we can use introspection of BasePaymentProcessor's
        # subclasses to find all installed payment processors
        from ecommerce.extensions.payment.processors.invoice_payment.processor import InvoicePayment
