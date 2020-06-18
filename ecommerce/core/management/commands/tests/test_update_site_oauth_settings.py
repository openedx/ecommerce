

from django.contrib.sites.models import Site
from django.core.management import call_command
from oscar.core.loading import get_model

from ecommerce.core.models import SiteConfiguration
from ecommerce.tests.testcases import TestCase

Partner = get_model('partner', 'Partner')


class UpdateSiteOauthSettingsCommandTests(TestCase):

    command_name = 'update_site_oauth_settings'

    def setUp(self):
        super(UpdateSiteOauthSettingsCommandTests, self).setUp()

        self.partner = 'fake'
        self.lms_url_root = 'http://fake.server'
        self.lms_public_url_root = 'http://public.fake.server'
        self.payment_processors = 'cybersource,paypal'
        self.discovery_api_url = 'https://fake.discovery.server/api/v1/'

        self.client_id = 'ecommerce-key'
        self.client_secret = 'ecommerce-secret'

        self.sso_client_id = 'sso_ecommerce-key'
        self.sso_client_secret = 'sso_ecommerce-secret'
        self.backend_service_client_id = 'backend_service_ecommerce-key'
        self.backend_service_client_secret = 'backend_service_ecommerce-secret'

    def _call_command(self, site_id,
                      sso_client_id=None, sso_client_secret=None,
                      backend_service_client_id=None, backend_service_client_secret=None):
        """
        Internal helper method for interacting with the create_or_update_site management command
        """
        # Required arguments
        command_args = [
            '--site-id={}'.format(site_id),
            '--sso-client-id={}'.format(sso_client_id),
            '--sso-client-secret={}'.format(sso_client_secret),
            '--backend-service-client-id={}'.format(backend_service_client_id),
            '--backend-service-client-secret={}'.format(backend_service_client_secret),
        ]

        call_command(self.command_name, *command_args)

    def _create_test_site_configuration(self, site):
        """
        Create a fake partner and site configuration for testing.
        """
        partner = Partner.objects.create(code=self.partner)
        site_configuration = SiteConfiguration.objects.create(
            site=site,
            partner=partner,
            lms_url_root=self.lms_url_root,
            payment_processors=self.payment_processors,
            discovery_api_url=self.discovery_api_url,
        )
        return site_configuration

    def test_update_site(self):  # pylint: disable=too-many-statements
        """
        Verify the command updates SiteConfiguration along with new OAuth2
        items without altering anything else.
        """
        site_domain = 'ecommerce-fake2.server'
        site = Site.objects.create(domain=site_domain)
        site_configuration = self._create_test_site_configuration(site=site)

        self._call_command(
            site_id=site.id,
            sso_client_id=self.sso_client_id,
            sso_client_secret=self.sso_client_secret,
            backend_service_client_id=self.backend_service_client_id,
            backend_service_client_secret=self.backend_service_client_secret,
        )

        site = Site.objects.get(id=site.id)
        site_configuration = site.siteconfiguration
        partner = Partner.objects.get(code=self.partner)

        # Spot check that nothing on the site object changed.
        self.assertEqual(site.domain, site_domain)

        # Confirm that all the new OAUTH2 (DOT) settings were added.
        self.assertEqual(
            site_configuration.oauth_settings['SOCIAL_AUTH_EDX_OAUTH2_ISSUERS'],
            [self.lms_url_root],
        )
        self.assertEqual(
            site_configuration.oauth_settings['SOCIAL_AUTH_EDX_OAUTH2_URL_ROOT'],
            'http://fake.server',
        )
        self.assertEqual(
            site_configuration.oauth_settings['SOCIAL_AUTH_EDX_OAUTH2_LOGOUT_URL'],
            'http://fake.server/logout',
        )
        self.assertEqual(
            site_configuration.oauth_settings['SOCIAL_AUTH_EDX_OAUTH2_KEY'],
            self.sso_client_id,
        )
        self.assertEqual(
            site_configuration.oauth_settings['SOCIAL_AUTH_EDX_OAUTH2_SECRET'],
            self.sso_client_secret,
        )
        self.assertEqual(
            site_configuration.oauth_settings['BACKEND_SERVICE_EDX_OAUTH2_KEY'],
            self.backend_service_client_id,
        )
        self.assertEqual(
            site_configuration.oauth_settings['BACKEND_SERVICE_EDX_OAUTH2_SECRET'],
            self.backend_service_client_secret,
        )

        # Spot check a few other fields to confirm nothing else changed.
        self.assertEqual(site_configuration.site, site)
        self.assertEqual(site_configuration.partner, partner)
        self.assertEqual(site_configuration.lms_url_root, self.lms_url_root)
        self.assertEqual(site_configuration.discovery_api_url, self.discovery_api_url)
