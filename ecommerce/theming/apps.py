"""
Module for code that should run during application startup
"""


from django.apps import AppConfig

from ecommerce.theming.core import enable_theming
from ecommerce.theming.helpers import is_comprehensive_theming_enabled


class ThemeAppConfig(AppConfig):
    """
    App Configurations for Theming.
    """
    name = 'ecommerce.theming'
    verbose_name = 'Theming'

    def ready(self):
        """
        startup run method, this method is called after the application has successfully initialized.
        Anything that needs to executed once (and only once) the theming app starts can be placed here.
        """
        if is_comprehensive_theming_enabled():
            # proceed only if comprehensive theming in enabled

            enable_theming()
