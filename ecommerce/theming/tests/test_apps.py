"""
Comprehensive Theming tests for Theme App Config.
"""
import mock

from django.conf import settings
from django.test import TestCase, override_settings

from path import Path

from ecommerce.theming.apps import ThemeAppConfig
from ecommerce import theming


class TestThemeAppConfig(TestCase):
    """
    Test comprehensive theming app config.
    """

    def test_theme_config_ready(self):
        """
        Tests enable theming is called in app config's ready method.
        """
        themes_dir = Path(settings.COMPREHENSIVE_THEME_DIR)

        # make sure locale paths were added to LOCALE_PATHS setting
        self.assertIn(themes_dir / "test-theme" / "conf" / "locale", settings.LOCALE_PATHS)
        self.assertIn(themes_dir / "test-theme-2" / "conf" / "locale", settings.LOCALE_PATHS)


class TestThemeAppConfigThemingDisabled(TestCase):
    """
    Test comprehensive theming app config.
    """
    def test_ready_enable_theming(self):
        """
        Tests that method `ready` invokes `enable_theming` method
        """
        themes_dir = Path(settings.COMPREHENSIVE_THEME_DIR)
        config = ThemeAppConfig('theming', theming)

        with mock.patch('ecommerce.theming.apps.enable_theming') as mock_enable_theming:
            config.ready()

            self.assertTrue(mock_enable_theming.called)
            mock_enable_theming.assert_called_once_with(themes_dir=themes_dir)

    @override_settings(ENABLE_COMPREHENSIVE_THEMING=False)
    def test_ready_with_theming_disabled(self):
        """
        Tests that method `ready` does not invoke `enable_theming` method when theming is disabled
        """
        config = ThemeAppConfig('theming', theming)

        with mock.patch('ecommerce.theming.apps.enable_theming') as mock_enable_theming:
            config.ready()

            self.assertFalse(mock_enable_theming.called)
