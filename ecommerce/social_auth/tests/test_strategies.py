"""Tests of social auth strategies."""
from django.conf import settings
from social.apps.django_app.default.models import DjangoStorage

from ecommerce.social_auth.strategies import CurrentSiteDjangoStrategy
from ecommerce.tests.testcases import TestCase


class CurrentSiteDjangoStrategyTests(TestCase):
    """Tests of the CurrentSiteDjangoStrategy."""

    def setUp(self):
        super(CurrentSiteDjangoStrategyTests, self).setUp()
        self.site.siteconfiguration.oauth_settings = {
            'SOCIAL_AUTH_EDX_OIDC_KEY': 'test-key'
        }
        self.strategy = CurrentSiteDjangoStrategy(DjangoStorage, self.request)

    def test_get_setting_from_siteconfiguration(self):
        """Test that a setting can be retrieved from the site configuration."""
        setting_name = 'SOCIAL_AUTH_EDX_OIDC_KEY'
        self.assertEqual(
            self.strategy.get_setting(setting_name),
            self.site.siteconfiguration.oauth_settings.get(setting_name)
        )

    def test_get_setting_from_django_settings(self):
        """Test that a setting can be retrieved from django settings if it doesn't exist in site configuration."""
        setting_name = 'SOCIAL_AUTH_EDX_OIDC_SECRET'
        self.assertEqual(
            self.strategy.get_setting(setting_name),
            getattr(settings, setting_name)
        )

    def test_get_setting_raises_exception_on_missing_setting(self):
        """Test that a setting that does not exist raises exception."""
        with self.assertRaises(KeyError):
            self.strategy.get_setting('FAKE_SETTING')
