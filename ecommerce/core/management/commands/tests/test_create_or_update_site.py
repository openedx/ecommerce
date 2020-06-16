

from ddt import data, ddt
from django.contrib.sites.models import Site
from django.core.management import CommandError, call_command
from oscar.core.loading import get_model

from ecommerce.tests.testcases import TestCase

Partner = get_model('partner', 'Partner')


@ddt
class CreateOrUpdateSiteCommandTests(TestCase):

    command_name = 'create_or_update_site'

    def setUp(self):
        super(CreateOrUpdateSiteCommandTests, self).setUp()

        self.partner = 'fake'
        self.lms_url_root = 'http://fake.server'
        self.lms_public_url_root = 'http://public.fake.server'
        self.payment_processors = 'cybersource,paypal'
        self.client_side_payment_processor = 'cybersource'
        self.sso_client_id = 'sso_ecommerce-key'
        self.sso_client_secret = 'sso_ecommerce-secret'
        self.backend_service_client_id = 'backend_service_ecommerce-key'
        self.backend_service_client_secret = 'backend_service_ecommerce-secret'
        self.segment_key = 'test-segment-key'
        self.from_email = 'site_from_email@example.com'
        self.payment_support_email = 'support@example.com'
        self.payment_support_url = 'http://fake.server/support'
        self.base_cookie_domain = '.fake.server'
        self.discovery_api_url = 'https://fake.discovery.server/api/v1/'

    def _check_site_configuration(self, site, partner):
        site_configuration = site.siteconfiguration
        self.assertEqual(site_configuration.site, site)
        self.assertEqual(site_configuration.partner, partner)
        self.assertEqual(site_configuration.partner.default_site, site)
        self.assertEqual(site_configuration.lms_url_root, self.lms_url_root)
        self.assertEqual(site_configuration.payment_processors, self.payment_processors)
        self.assertEqual(site_configuration.client_side_payment_processor, self.client_side_payment_processor)
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
        if 'SOCIAL_AUTH_EDX_OAUTH2_PUBLIC_URL_ROOT' in site_configuration.oauth_settings:
            self.assertEqual(
                site_configuration.oauth_settings['SOCIAL_AUTH_EDX_OAUTH2_PUBLIC_URL_ROOT'],
                'http://public.fake.server',
            )
        if 'SOCIAL_AUTH_EDX_OAUTH2_KEY' in site_configuration.oauth_settings:
            self.assertEqual(
                site_configuration.oauth_settings['SOCIAL_AUTH_EDX_OAUTH2_KEY'],
                self.sso_client_id,
            )
        if 'SOCIAL_AUTH_EDX_OAUTH2_SECRET' in site_configuration.oauth_settings:
            self.assertEqual(
                site_configuration.oauth_settings['SOCIAL_AUTH_EDX_OAUTH2_SECRET'],
                self.sso_client_secret,
            )
        if 'BACKEND_SERVICE_EDX_OAUTH2_KEY' in site_configuration.oauth_settings:
            self.assertEqual(
                site_configuration.oauth_settings['BACKEND_SERVICE_EDX_OAUTH2_KEY'],
                self.backend_service_client_id,
            )
        if 'BACKEND_SERVICE_EDX_OAUTH2_SECRET' in site_configuration.oauth_settings:
            self.assertEqual(
                site_configuration.oauth_settings['BACKEND_SERVICE_EDX_OAUTH2_SECRET'],
                self.backend_service_client_secret,
            )
        self.assertEqual(site_configuration.segment_key, self.segment_key)
        self.assertEqual(site_configuration.from_email, self.from_email)
        self.assertEqual(site_configuration.discovery_api_url, self.discovery_api_url)

    def _call_command(self,
                      site_domain,
                      partner_code,
                      lms_url_root,
                      sso_client_id,
                      sso_client_secret,
                      backend_service_client_id,
                      backend_service_client_secret,
                      from_email,
                      lms_public_url_root=None,
                      site_id=None,
                      site_name=None,
                      partner_name=None,
                      payment_processors=None,
                      segment_key=None,
                      enable_enrollment_codes=False,
                      payment_support_email=None,
                      payment_support_url=None,
                      send_refund_notifications=False,
                      client_side_payment_processor=None,
                      disable_otto_receipt_page=False,
                      base_cookie_domain=None,
                      discovery_api_url=None):
        """
        Internal helper method for interacting with the create_or_update_site management command
        """
        # Required arguments
        command_args = [
            '--site-domain={site_domain}'.format(site_domain=site_domain),
            '--partner-code={partner_code}'.format(partner_code=partner_code),
            '--lms-url-root={lms_url_root}'.format(lms_url_root=lms_url_root),
            '--sso-client-id={}'.format(sso_client_id),
            '--sso-client-secret={}'.format(sso_client_secret),
            '--backend-service-client-id={}'.format(backend_service_client_id),
            '--backend-service-client-secret={}'.format(backend_service_client_secret),
            '--from-email={from_email}'.format(from_email=from_email)
        ]

        # Optional arguments
        if site_id:
            command_args.append('--site-id={site_id}'.format(site_id=site_id))
        if site_name:
            command_args.append('--site-name={site_name}'.format(site_name=site_name))
        if lms_public_url_root:
            command_args.append('--lms-public-url-root={lms_public_url_root}'.format(
                lms_public_url_root=lms_public_url_root
            ))
        if partner_name:
            command_args.append('--partner-name={partner_name}'.format(partner_name=partner_name))
        if payment_processors:
            command_args.append('--payment-processors={payment_processors}'.format(
                payment_processors=payment_processors
            ))
        if client_side_payment_processor:
            command_args.append('--client-side-payment-processor={}'.format(client_side_payment_processor))
        if segment_key:
            command_args.append('--segment-key={segment_key}'.format(segment_key=segment_key))
        if enable_enrollment_codes:
            command_args.append('--enable-enrollment-codes={enable_enrollment_codes}'.format(
                enable_enrollment_codes=enable_enrollment_codes
            ))
        if payment_support_email:
            command_args.append('--payment-support-email={payment_support_email}'.format(
                payment_support_email=payment_support_email
            ))
        if payment_support_url:
            command_args.append('--payment-support-url={payment_support_url}'.format(
                payment_support_url=payment_support_url
            ))
        if base_cookie_domain:
            command_args.append('--base-cookie-domain={base_cookie_domain}'.format(
                base_cookie_domain=base_cookie_domain
            ))

        if send_refund_notifications:
            command_args.append('--send-refund-notifications')

        if disable_otto_receipt_page:
            command_args.append('--disable-otto-receipt-page')

        if discovery_api_url:
            command_args.append('--discovery_api_url={discovery_api_url}'.format(
                discovery_api_url=discovery_api_url
            ))

        call_command(self.command_name, *command_args)

    def test_create_site(self):
        """ Verify the command creates Site, Partner, and SiteConfiguration. """
        site_domain = 'ecommerce-fake1.server'

        self._call_command(
            site_domain=site_domain,
            partner_code=self.partner,
            lms_url_root=self.lms_url_root,
            client_side_payment_processor=self.client_side_payment_processor,
            payment_processors=self.payment_processors,
            sso_client_id=self.sso_client_id,
            sso_client_secret=self.sso_client_secret,
            backend_service_client_id=self.backend_service_client_id,
            backend_service_client_secret=self.backend_service_client_secret,
            segment_key=self.segment_key,
            from_email=self.from_email,
            discovery_api_url=self.discovery_api_url,
        )

        site = Site.objects.get(domain=site_domain)
        partner = Partner.objects.get(code=self.partner)

        self._check_site_configuration(site, partner)
        self.assertFalse(site.siteconfiguration.enable_enrollment_codes)
        self.assertFalse(site.siteconfiguration.send_refund_notifications)
        self.assertEqual(site.siteconfiguration.base_cookie_domain, '')

    def test_update_site(self):
        """ Verify the command updates Site and creates Partner, and SiteConfiguration """
        site_domain = 'ecommerce-fake2.server'
        updated_site_domain = 'ecommerce-fake3.server'
        updated_site_name = 'Fake Ecommerce Server'
        site = Site.objects.create(domain=site_domain)

        self._call_command(
            site_id=site.id,
            site_domain=updated_site_domain,
            site_name=updated_site_name,
            partner_code=self.partner,
            lms_url_root=self.lms_url_root,
            payment_processors=self.payment_processors,
            client_side_payment_processor=self.client_side_payment_processor,
            sso_client_id=self.sso_client_id,
            sso_client_secret=self.sso_client_secret,
            backend_service_client_id=self.backend_service_client_id,
            backend_service_client_secret=self.backend_service_client_secret,
            segment_key=self.segment_key,
            from_email=self.from_email,
            enable_enrollment_codes=True,
            payment_support_email=self.payment_support_email,
            payment_support_url=self.payment_support_url,
            send_refund_notifications=True,
            disable_otto_receipt_page=True,
            base_cookie_domain=self.base_cookie_domain,
            discovery_api_url=self.discovery_api_url,
        )

        site = Site.objects.get(id=site.id)
        partner = Partner.objects.get(code=self.partner)

        self.assertEqual(site.domain, updated_site_domain)
        self.assertEqual(site.name, updated_site_name)
        self._check_site_configuration(site, partner)

        site_configuration = site.siteconfiguration
        self.assertTrue(site_configuration.enable_enrollment_codes)
        self.assertEqual(site_configuration.payment_support_email, self.payment_support_email)
        self.assertEqual(site_configuration.payment_support_url, self.payment_support_url)
        self.assertTrue(site_configuration.send_refund_notifications)
        self.assertEqual(site.siteconfiguration.base_cookie_domain, self.base_cookie_domain)

    def test_update_site_with_updated_oauth(self):
        """
        Verify the command updates Site and creates Partner, and SiteConfiguration along with new OAuth2 items
        """
        site_domain = 'ecommerce-fake2.server'
        updated_site_domain = 'ecommerce-fake3.server'
        updated_site_name = 'Fake Ecommerce Server'
        site = Site.objects.create(domain=site_domain)

        self._call_command(
            site_id=site.id,
            site_domain=updated_site_domain,
            site_name=updated_site_name,
            partner_code=self.partner,
            lms_url_root=self.lms_url_root,
            lms_public_url_root=self.lms_public_url_root,
            payment_processors=self.payment_processors,
            client_side_payment_processor=self.client_side_payment_processor,
            sso_client_id=self.sso_client_id,
            sso_client_secret=self.sso_client_secret,
            backend_service_client_id=self.backend_service_client_id,
            backend_service_client_secret=self.backend_service_client_secret,
            segment_key=self.segment_key,
            from_email=self.from_email,
            enable_enrollment_codes=True,
            payment_support_email=self.payment_support_email,
            payment_support_url=self.payment_support_url,
            send_refund_notifications=True,
            disable_otto_receipt_page=True,
            base_cookie_domain=self.base_cookie_domain,
            discovery_api_url=self.discovery_api_url,
        )

        site = Site.objects.get(id=site.id)
        partner = Partner.objects.get(code=self.partner)

        self.assertEqual(site.domain, updated_site_domain)
        self.assertEqual(site.name, updated_site_name)
        self._check_site_configuration(site, partner)

        site_configuration = site.siteconfiguration
        self.assertTrue(site_configuration.enable_enrollment_codes)
        self.assertEqual(site_configuration.payment_support_email, self.payment_support_email)
        self.assertEqual(site_configuration.payment_support_url, self.payment_support_url)
        self.assertTrue(site_configuration.send_refund_notifications)
        self.assertEqual(site.siteconfiguration.base_cookie_domain, self.base_cookie_domain)

    @data(
        ['--site-id=1'],
        ['--site-id=1', '--site-name=fake.server'],
        ['--site-id=1', '--site-name=fake.server', '--partner-name=fake_partner'],
        ['--site-id=1', '--site-domain=fake.server', '--partner-name=fake_partner',
         '--theme-scss-path=site/sass/css/'],
        ['--site-id=1', '--site-domain=fake.server', '--partner-name=fake_partner',
         '--theme-scss-path=site/sass/css/', '--payment-processors=cybersource'],
        ['--site-id=1', '--site-domain=fake.server', '--partner-name=fake_partner',
         '--theme-scss-path=site/sass/css/', '--payment-processors=cybersource',
         '--segment-key=abc'],
        ['--site-id=1', '--site-domain=fake.server', '--partner-name=fake_partner',
         '--theme-scss-path=site/sass/css/', '--payment-processors=cybersource',
         '--segment-key=abc', '--partner-code=fake_partner'],
        ['--site-id=1', '--site-domain=fake.server', '--partner-name=fake_partner',
         '--theme-scss-path=site/sass/css/', '--payment-processors=cybersource',
         '--segment-key=abc', '--partner-code=fake_partner', '--lms-url-root=lms.test.fake'],
        ['--site-id=1', '--site-domain=fake.server', '--partner-name=fake_partner',
         '--theme-scss-path=site/sass/css/', '--payment-processors=cybersource',
         '--segment-key=abc', '--partner-code=fake_partner', '--lms-url-root=lms.test.fake',
         '--sso-client-id=1'],
        ['--site-id=1', '--site-domain=fake.server', '--partner-name=fake_partner',
         '--theme-scss-path=site/sass/css/', '--payment-processors=cybersource',
         '--segment-key=abc', '--partner-code=fake_partner', '--lms-url-root=lms.test.fake',
         '--sso-client-id=1', '--sso-client-secret=secret'],
        ['--site-id=1', '--site-domain=fake.server', '--partner-name=fake_partner',
         '--theme-scss-path=site/sass/css/', '--payment-processors=cybersource',
         '--segment-key=abc', '--partner-code=fake_partner', '--lms-url-root=lms.test.fake',
         '--sso-client-id=1', '--sso-client-secret=secret', '--backend-service-client-id=1'],
        ['--site-id=1', '--site-domain=fake.server', '--partner-name=fake_partner',
         '--theme-scss-path=site/sass/css/', '--payment-processors=cybersource',
         '--segment-key=abc', '--partner-code=fake_partner', '--lms-url-root=lms.test.fake',
         '--sso-client-id=1', '--sso-client-secret=secret', '--backend-service-client-id=1',
         '--backend-service-client-secret=secret'],
        ['--site-id=1', '--site-domain=fake.server', '--partner-name=fake_partner',
         '--theme-scss-path=site/sass/css/', '--payment-processors=cybersource',
         '--segment-key=abc', '--partner-code=fake_partner', '--lms-url-root=lms.test.fake',
         '--sso-client-id=1', '--sso-client-secret=secret', '--backend-service-client-id=1',
         '--backend-service-client-secret=secret', '--from-email=test@example.fake'],
    )
    def test_missing_arguments(self, command_args):
        """ Verify CommandError is raised when required arguments are missing """
        with self.assertRaises(CommandError):
            call_command(self.command_name, *command_args)
