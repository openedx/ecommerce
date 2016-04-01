from django.db import models
from django.contrib.sites.models import Site


class SiteTheme(models.Model):
    """
    This is where the information about the site's theme gets stored to the db.

    Fields:
        site (ForeignKey): Foreign Key field pointing to django Site model
        theme_dir_name (CharField): Contains directory name for any site's theme (e.g. 'red-theme')
    """
    site = models.ForeignKey(Site, related_name='themes')
    theme_dir_name = models.CharField(max_length=255)
