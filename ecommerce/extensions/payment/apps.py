

from oscar.apps.payment import apps


class PaymentConfig(apps.PaymentConfig):
    name = 'ecommerce.extensions.payment'

    def ready(self):
        super().ready()
        # Register signal handlers
        # noinspection PyUnresolvedReferences
        import ecommerce.extensions.payment.signals  # pylint: disable=unused-import, import-outside-toplevel

    def get_urls(self):
        """Returns the URL patterns for the Payment Application."""
        from ecommerce.extensions.payment.urls import urlpatterns  # pylint: disable=import-outside-toplevel
        return self.post_process_urls(urlpatterns)
