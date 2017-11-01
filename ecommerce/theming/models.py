import logging

from django.conf import settings
from django.contrib.sites.models import Site
from django.db import models

logger = logging.getLogger(__name__)


class SiteTheme(models.Model):
    """
    This is where the information about the site's theme gets stored to the db.

    Fields:
        site (ForeignKey): Foreign Key field pointing to django Site model
        theme_dir_name (CharField): Contains directory name for any site's theme (e.g. 'red-theme')
    """
    site = models.ForeignKey(Site, related_name='themes', on_delete=models.CASCADE)
    theme_dir_name = models.CharField(max_length=255)

    @staticmethod
    def get_theme(site):
        """
        Get SiteTheme object for given site, returns default site theme if it can not
        find a theme for the given site and `DEFAULT_SITE_THEME` setting has a proper value.

        Args:
            site (django.contrib.sites.models.Site): site object related to the current site.

        Returns:
            SiteTheme object for given site or a default site set by `DEFAULT_SITE_THEME`
        """
        if not site:
            logger.warning('A site must be specified when retrieving a theme.')
            return None

        logger.info('Retrieving theme for site [%d]...', site.id)
        theme = site.themes.first()

        if theme:
            logger.info(
                'Setting theme for site [%d] to theme [%d] with assets in [%s]',
                site.id, theme.id, theme.theme_dir_name
            )

        else:
            default_theme_dir = settings.DEFAULT_SITE_THEME
            if default_theme_dir:
                logger.info('No theme found for site [%d]. Using default assets in [%s]', site.id, default_theme_dir)
                theme = SiteTheme(site=site, theme_dir_name=settings.DEFAULT_SITE_THEME)
            else:
                logger.error('No default theme has been defined!')

        return theme
