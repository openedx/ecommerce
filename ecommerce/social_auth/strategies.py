from django.conf import settings

from social.strategies.django_strategy import DjangoStrategy


class CurrentSiteDjangoStrategy(DjangoStrategy):
    """
    Python Social Auth strategy which accounts for the current
    Site when enabling third party authentication.
    """

    def get_setting(self, name):
        # First check the current SiteConfiguration for the setting
        setting = self.request.site.siteconfiguration.oauth_settings.get(name)
        if not setting:
            # Then check Django settings for the setting
            setting = getattr(settings, name)
        return setting
