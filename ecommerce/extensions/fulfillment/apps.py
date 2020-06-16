

from django.apps import AppConfig


class FulfillmentAppConfig(AppConfig):
    name = 'ecommerce.extensions.fulfillment'
    verbose_name = 'Fulfillment'

    def ready(self):
        super().ready()

        # noinspection PyUnresolvedReferences
        import ecommerce.extensions.fulfillment.signals  # pylint: disable=unused-import, import-outside-toplevel
