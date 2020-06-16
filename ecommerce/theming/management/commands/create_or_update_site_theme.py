"""
Creates or updates a Site and Site Theme.
"""
import logging

from django.contrib.sites.models import Site
from django.core.management import BaseCommand

from ecommerce.theming.models import SiteTheme

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Create or update Site and SiteTheme'

    def add_arguments(self, parser):
        parser.add_argument('--site-id',
                            action='store',
                            dest='site_id',
                            type=int,
                            help='ID of the Site to update.')
        parser.add_argument('--site-domain',
                            action='store',
                            dest='site_domain',
                            type=str,
                            required=True,
                            help='Domain of the Site to create or update.')
        parser.add_argument('--site-name',
                            action='store',
                            dest='site_name',
                            type=str,
                            default='',
                            help='Name of the Site to create or update.')
        parser.add_argument('--site-theme',
                            action='store',
                            dest='site_theme',
                            type=str,
                            required=True,
                            help='Name of the theme to apply to the site.')

    def handle(self, *args, **options):
        site_id = options.get('site_id')
        site_domain = options.get('site_domain')
        site_name = options.get('site_name')
        site_theme = options.get('site_theme')

        try:
            site = Site.objects.get(id=site_id)
        except Site.DoesNotExist:
            site, site_created = Site.objects.get_or_create(domain=site_domain)
            if site_created:
                logger.info('Site created with domain %s', site_domain)

        site.domain = site_domain
        if site_name:
            site.name = site_name
        site.save()

        _, created = SiteTheme.objects.update_or_create(
            site=site,
            defaults={
                'theme_dir_name': site_theme,
            }
        )
        logger.info('Site Theme %s with theme "%s"', "created" if created else "updated", site_theme)
