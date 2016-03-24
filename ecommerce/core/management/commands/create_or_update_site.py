""" Creates or updates a Site including Partner and SiteConfiguration data. """

from __future__ import unicode_literals
import logging

from django.contrib.sites.models import Site
from django.core.management import BaseCommand
from oscar.core.loading import get_model

from ecommerce.core.models import SiteConfiguration

logger = logging.getLogger(__name__)
Partner = get_model('partner', 'Partner')


class Command(BaseCommand):
    help = 'Create or update Site, Partner, and SiteConfiguration'

    def add_arguments(self, parser):
        parser.add_argument('-i', '--site-id',
                            action='store',
                            dest='site_id',
                            type=int,
                            help='ID of the Site to update.')
        parser.add_argument('-d', '--site-domain',
                            action='store',
                            dest='site_domain',
                            type=str,
                            required=True,
                            help='Domain of the Site to create or update.')
        parser.add_argument('-n', '--site-name',
                            action='store',
                            dest='site_name',
                            type=str,
                            default='',
                            help='Name of the Site to create or update.')
        parser.add_argument('-c', '--partner-code',
                            action='store',
                            dest='partner_code',
                            type=str,
                            required=True,
                            help='Partner code to select/create and associate with site.')
        parser.add_argument('-p', '--partner-name',
                            action='store',
                            dest='partner_name',
                            type=str,
                            default='',
                            help='Partner name to select/create and associate with site.')
        parser.add_argument('-l', '--lms-url-root',
                            action='store',
                            dest='lms_url_root',
                            type=str,
                            required=True,
                            help='Root URL of LMS (e.g. https://localhost:8000)')
        parser.add_argument('-t', '--theme-scss-path',
                            action='store',
                            dest='theme_scss_path',
                            type=str,
                            default='',
                            help='Path to theme SCSS relative to STATIC_DIR (e.g. sass/themes/edx.scss)')
        parser.add_argument('-m', '--payment-processors',
                            action='store',
                            dest='payment_processors',
                            type=str,
                            default='',
                            help='Comma-delimited list of payment processors (e.g. cybersource,paypal)')
        parser.add_argument('-k', '--client-id',
                            action='store',
                            dest='client_id',
                            type=str,
                            required=True,
                            help='client ID')
        parser.add_argument('-s', '--client-secret',
                            action='store',
                            dest='client_secret',
                            type=str,
                            required=True,
                            help='client secret')

    def handle(self, *args, **options):
        site_id = options.get('site_id')
        site_domain = options.get('site_domain')
        site_name = options.get('site_name')
        partner_code = options.get('partner_code')
        partner_name = options.get('partner_name')
        lms_url_root = options.get('lms_url_root')
        client_id = options.get('client_id')
        client_secret = options.get('client_secret')

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

        partner, partner_created = Partner.objects.get_or_create(code=partner_code)
        if partner_created:
            partner.name = partner_name
            partner.short_code = partner_code
            partner.save()
            logger.info('Partner created with code %s', partner_code)

        _, _ = SiteConfiguration.objects.get_or_create(
            site=site,
            defaults={
                'partner': partner,
                'lms_url_root': lms_url_root,
                'theme_scss_path': options['theme_scss_path'],
                'payment_processors': options['payment_processors'],
                'oauth_settings': {
                    'SOCIAL_AUTH_EDX_OIDC_URL_ROOT': '{lms_url_root}/oauth2'.format(lms_url_root=lms_url_root),
                    'SOCIAL_AUTH_EDX_OIDC_KEY': client_id,
                    'SOCIAL_AUTH_EDX_OIDC_SECRET': client_secret,
                    'SOCIAL_AUTH_EDX_OIDC_ID_TOKEN_DECRYPTION_KEY': client_secret,
                    'SOCIAL_AUTH_EDX_OIDC_ISSUERS': [lms_url_root]
                }
            }
        )
