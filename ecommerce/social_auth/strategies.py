import logging

from auth_backends.strategies import EdxDjangoStrategy

logger = logging.getLogger(__name__)


class CurrentSiteDjangoStrategy(EdxDjangoStrategy):
    """
    Python Social Auth strategy which accounts for the current
    Site when enabling third party authentication.
    """

    def get_setting(self, name):
        site = self.request.site

        # Check the request's associated SiteConfiguration for the setting
        value = site.siteconfiguration.oauth_settings.get(name)

        if value:
            logger.info('Retrieved setting [%s] for site [%d] from SiteConfiguration', name, site.id)
        else:
            value = super(CurrentSiteDjangoStrategy, self).get_setting(name)
            logger.info('Retrieved setting [%s] for site [%d] from settings', name, site.id)

        return value
