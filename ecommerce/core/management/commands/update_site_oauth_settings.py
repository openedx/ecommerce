"""
Updates a SiteConfiguration to include new DOT-specific OAUTH2 settings.
"""
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
        parser.add_argument('--site-id',
                            action='store',
                            dest='site_id',
                            required=True,
                            type=int,
                            help='ID of the Site to update.')
        parser.add_argument('--sso-client-id',
                            action='store',
                            dest='sso_client_id',
                            required=True,
                            type=str,
                            help='SSO client ID for individual user auth')
        parser.add_argument('--sso-client-secret',
                            action='store',
                            dest='sso_client_secret',
                            required=True,
                            type=str,
                            help='SSO client secret for individual user auth')
        parser.add_argument('--backend-service-client-id',
                            action='store',
                            dest='backend_service_client_id',
                            required=True,
                            type=str,
                            help='Backend-service client ID for IDA-to-IDA auth')
        parser.add_argument('--backend-service-client-secret',
                            action='store',
                            dest='backend_service_client_secret',
                            required=True,
                            type=str,
                            help='Backend-service client secret for IDA-to-IDA auth')

    def handle(self, *args, **options):
        site_id = options.get('site_id')
        sso_client_id = options.get('sso_client_id')
        sso_client_secret = options.get('sso_client_secret')
        backend_service_client_id = options.get('backend_service_client_id')
        backend_service_client_secret = options.get('backend_service_client_secret')

        site = Site.objects.get(id=site_id)
        site_configuration = SiteConfiguration.objects.get(site=site)
        oauth_settings = site_configuration.oauth_settings
        lms_url_root = site_configuration.lms_url_root

        oauth_settings.update({
            'SOCIAL_AUTH_EDX_OAUTH2_URL_ROOT': lms_url_root,
            'SOCIAL_AUTH_EDX_OAUTH2_LOGOUT_URL': '{lms_url_root}/logout'.format(lms_url_root=lms_url_root),
            'SOCIAL_AUTH_EDX_OAUTH2_ISSUERS': [lms_url_root],
            'SOCIAL_AUTH_EDX_OAUTH2_KEY': sso_client_id,
            'SOCIAL_AUTH_EDX_OAUTH2_SECRET': sso_client_secret,
            'BACKEND_SERVICE_EDX_OAUTH2_KEY': backend_service_client_id,
            'BACKEND_SERVICE_EDX_OAUTH2_SECRET': backend_service_client_secret,
        })

        site_configuration.save()
