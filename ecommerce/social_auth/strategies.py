

from auth_backends.strategies import EdxDjangoStrategy


class CurrentSiteDjangoStrategy(EdxDjangoStrategy):
    """
    Python Social Auth strategy which accounts for the current
    Site when enabling third party authentication.
    """

    def get_setting(self, name):
        # Check the request's associated SiteConfiguration for the setting
        value = self.request.site.siteconfiguration.oauth_settings.get(name)

        if not value:
            value = super(CurrentSiteDjangoStrategy, self).get_setting(name)

        return value
