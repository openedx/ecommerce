

from django.conf import settings
from oscar.apps.analytics import apps


class AnalyticsConfig(apps.AnalyticsConfig):
    name = 'ecommerce.extensions.analytics'

    def ready(self):
        if settings.INSTALL_DEFAULT_ANALYTICS_RECEIVERS:
            from oscar.apps.analytics import receivers  # pylint: disable=unused-import, import-outside-toplevel
