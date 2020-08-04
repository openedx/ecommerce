"""
Comprehensive Theming tests for core functionality.
"""


from django.conf import settings
from django.test import override_settings
from path import Path

from ecommerce.tests.testcases import TestCase
from ecommerce.theming.core import enable_theming


class TestCore(TestCase):
    """
    Test comprehensive theming helper functions.
    """

    def test_enable_theming(self):
        """
        Tests for enable_theming method.
        """
        themes_dirs = settings.COMPREHENSIVE_THEME_DIRS

        expected_locale_paths = (
            themes_dirs[0] / "test-theme" / "conf" / "locale",
            themes_dirs[0] / "test-theme-2" / "conf" / "locale",
            themes_dirs[1] / "test-theme-3" / "conf" / "locale",
        ) + settings.LOCALE_PATHS

        enable_theming()

        self.assertCountEqual(expected_locale_paths, settings.LOCALE_PATHS)

    def test_enable_theming_red_theme(self):
        """
        Tests that locale path is added only if it exists.
        """
        # Themes directory containing red-theme
        themes_dir = settings.DJANGO_ROOT + "/themes"

        # Note: red-theme does not contain translations dir
        red_theme = Path(themes_dir + "/red-theme")
        with override_settings(COMPREHENSIVE_THEME_DIRS=[red_theme.dirname()]):
            enable_theming()

            # Test that locale path is added only if it exists
            self.assertNotIn(red_theme / "conf" / "locale", settings.LOCALE_PATHS)
