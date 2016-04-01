from oscar.apps.payment import config


class PaymentConfig(config.PaymentConfig):
    name = 'ecommerce.extensions.payment'

    def ready(self):
        # Register signal handlers
        # noinspection PyUnresolvedReferences
        import ecommerce.extensions.payment.signals  # pylint: disable=unused-variable
