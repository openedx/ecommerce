from django.conf import settings
from oscar.apps.payment import config
import paypalrestsdk


class PaymentConfig(config.PaymentConfig):
    name = 'ecommerce.extensions.payment'

    def ready(self):
        paypal_configuration = settings.PAYMENT_PROCESSOR_CONFIG.get('paypal')
        if paypal_configuration:
            # Initialize the PayPal REST SDK
            paypalrestsdk.configure({
                'mode': paypal_configuration['mode'],
                'client_id': paypal_configuration['client_id'],
                'client_secret': paypal_configuration['client_secret']
            })

        # Register signal handlers
        # noinspection PyUnresolvedReferences
        import ecommerce.extensions.payment.signals  # pylint: disable=unused-variable
