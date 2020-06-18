"""
Comprehensive Theming tests for Theme App Config.
"""


import mock
from django.conf import settings
from django.test import override_settings

from ecommerce import theming
from ecommerce.tests.testcases import TestCase
from ecommerce.theming.apps import ThemeAppConfig


class TestThemeAppConfig(TestCase):
    """
    Test comprehensive theming app config.
    """

    def test_theme_config_ready(self):
        """
        Tests enable theming is called in app config's ready method.
        """
        themes_dirs = settings.COMPREHENSIVE_THEME_DIRS

        # make sure locale paths were added to LOCALE_PATHS setting
        self.assertIn(themes_dirs[0] / "test-theme" / "conf" / "locale", settings.LOCALE_PATHS)
        self.assertIn(themes_dirs[0] / "test-theme-2" / "conf" / "locale", settings.LOCALE_PATHS)

        self.assertIn(themes_dirs[1] / "test-theme-3" / "conf" / "locale", settings.LOCALE_PATHS)


class TestThemeAppConfigThemingDisabled(TestCase):
    """
    Test comprehensive theming app config.
    """
    def test_ready_enable_theming(self):
        """
        Tests that method `ready` invokes `enable_theming` method
        """
        config = ThemeAppConfig('theming', theming)

        with mock.patch('ecommerce.theming.apps.enable_theming') as mock_enable_theming:
            config.ready()
            self.assertTrue(mock_enable_theming.called)

    @override_settings(ENABLE_COMPREHENSIVE_THEMING=False)
    def test_ready_with_theming_disabled(self):
        """
        Tests that method `ready` does not invoke `enable_theming` method when theming is disabled
        """
        config = ThemeAppConfig('theming', theming)

        with mock.patch('ecommerce.theming.apps.enable_theming') as mock_enable_theming:
            config.ready()

            self.assertFalse(mock_enable_theming.called)
