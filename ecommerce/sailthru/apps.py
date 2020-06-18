

from django.apps import AppConfig


class SailthruAppConfig(AppConfig):
    name = 'ecommerce.sailthru'
    verbose_name = 'Sailthru'

    def ready(self):
        super(SailthruAppConfig, self).ready()

        # noinspection PyUnresolvedReferences
        import ecommerce.sailthru.signals  # pylint: disable=unused-import, import-outside-toplevel
