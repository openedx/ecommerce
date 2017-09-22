from django.apps import AppConfig


class FulfillmentAppConfig(AppConfig):
    name = 'ecommerce.extensions.fulfillment'
    verbose_name = 'Fulfillment'

    def ready(self):
        super(FulfillmentAppConfig, self).ready()

        # noinspection PyUnresolvedReferences
        import ecommerce.extensions.fulfillment.signals  # pylint: disable=unused-variable
