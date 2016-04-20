from __future__ import unicode_literals

from ddt import ddt, data
from django.contrib.sites.models import Site
from django.core.management import call_command, CommandError
from oscar.core.loading import get_model

from ecommerce.tests.testcases import TestCase

Partner = get_model('partner', 'Partner')


@ddt
class CreateOrUpdateSiteCommandTests(TestCase):
    command = 'create_or_update_site'

    def setUp(self):
        super(CreateOrUpdateSiteCommandTests, self).setUp()

        self.partner = 'fake'
        self.lms_url_root = 'http://fake.server'
        self.theme_scss_path = 'sass/themes/edx.scss'
        self.payment_processors = 'cybersource,paypal'
        self.client_id = 'ecommerce-key'
        self.client_secret = 'ecommerce-secret'
        self.segment_key = 'test-segment-key'

    def _check_site_configuration(self, site, partner):
        site_configuration = site.siteconfiguration
        self.assertEqual(site_configuration.site, site)
        self.assertEqual(site_configuration.partner, partner)
        self.assertEqual(site_configuration.lms_url_root, self.lms_url_root)
        self.assertEqual(site_configuration.theme_scss_path, self.theme_scss_path)
        self.assertEqual(site_configuration.payment_processors, self.payment_processors)
        self.assertEqual(site_configuration.oauth_settings['SOCIAL_AUTH_EDX_OIDC_KEY'], self.client_id)
        self.assertEqual(site_configuration.oauth_settings['SOCIAL_AUTH_EDX_OIDC_SECRET'], self.client_secret)
        self.assertEqual(site_configuration.segment_key, self.segment_key)

    def test_create_site(self):
        """ Verify the command creates Site, Partner, and SiteConfiguration. """
        site_domain = 'ecommerce-fake1.server'
        call_command(
            self.command,
            '--site-domain={domain}'.format(domain=site_domain),
            '--partner-code={partner}'.format(partner=self.partner),
            '--lms-url-root={lms_url_root}'.format(lms_url_root=self.lms_url_root),
            '--theme-scss-path={theme_scss_path}'.format(theme_scss_path=self.theme_scss_path),
            '--payment-processors={payment_processors}'.format(payment_processors=self.payment_processors),
            '--client-id={client_id}'.format(client_id=self.client_id),
            '--client-secret={client_secret}'.format(client_secret=self.client_secret),
            '--segment-key={segment_key}'.format(segment_key=self.segment_key)
        )

        site = Site.objects.get(domain=site_domain)
        partner = Partner.objects.get(code=self.partner)

        self._check_site_configuration(site, partner)

    def test_update_site(self):
        """ Verify the command updates Site and creates Partner, and SiteConfiguration """
        site_domain = 'ecommerce-fake2.server'
        updated_site_domain = 'ecommerce-fake3.server'
        updated_site_name = 'Fake Ecommerce Server'
        site = Site.objects.create(domain=site_domain)
        call_command(
            self.command,
            '--site-id={site_id}'.format(site_id=site.id),
            '--site-domain={domain}'.format(domain=updated_site_domain),
            '--site-name={site_name}'.format(site_name=updated_site_name),
            '--partner-code={partner}'.format(partner=self.partner),
            '--lms-url-root={lms_url_root}'.format(lms_url_root=self.lms_url_root),
            '--theme-scss-path={theme_scss_path}'.format(theme_scss_path=self.theme_scss_path),
            '--payment-processors={payment_processors}'.format(payment_processors=self.payment_processors),
            '--client-id={client_id}'.format(client_id=self.client_id),
            '--client-secret={client_secret}'.format(client_secret=self.client_secret),
            '--segment-key={segment_key}'.format(segment_key=self.segment_key)
        )

        site = Site.objects.get(id=site.id)
        partner = Partner.objects.get(code=self.partner)

        self.assertEqual(site.domain, updated_site_domain)
        self.assertEqual(site.name, updated_site_name)
        self._check_site_configuration(site, partner)

    @data(
        ['--site-id=1'],
        ['--site-id=1', '--site-domain=fake.server'],
        ['--site-id=1', '--site-domain=fake.server', '--partner-code=fake_partner'],
        ['--site-id=1', '--site-domain=fake.server', '--partner-code=fake_partner',
         '--lms-url-root=http://fake.server'],
        ['--site-id=1', '--site-domain=fake.server', '--partner-code=fake_partner',
         '--lms-url-root=http://fake.server', '--client-id=fake'],
    )
    def test_missing_arguments(self, arguments):
        """ Verify CommandError is raised when required arguments are missing """
        with self.assertRaises(CommandError):
            call_command(self.command, *arguments)
