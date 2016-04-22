"""
Comprehensive Theming tests for core functionality.
"""
from django.conf import settings
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
        themes_dir = Path(settings.COMPREHENSIVE_THEME_DIR)

        expected_locale_paths = (
            themes_dir / "test-theme" / "conf" / "locale",
            themes_dir / "test-theme-2" / "conf" / "locale",
        ) + settings.LOCALE_PATHS

        enable_theming(settings.COMPREHENSIVE_THEME_DIR)

        self.assertItemsEqual(expected_locale_paths, settings.LOCALE_PATHS)

    def test_enable_theming_red_theme(self):
        """
        Tests that locale path is added only if it exists.
        """
        # Themes directory containing red-theme
        themes_dir = settings.DJANGO_ROOT + "/themes"

        # Note: red-theme does not contain translations dir
        red_theme = Path(themes_dir + "/red-theme")
        enable_theming(red_theme.dirname())

        # Test that locale path is added only if it exists
        self.assertNotIn(red_theme / "conf" / "locale", settings.LOCALE_PATHS)
