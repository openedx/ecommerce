"""
Tests of comprehensive theming.
"""


from django.conf import ImproperlyConfigured, settings
from django.test import override_settings
from mock import patch

from ecommerce.tests.testcases import TestCase
from ecommerce.theming.helpers import (
    Theme,
    get_all_theme_template_dirs,
    get_current_site_theme,
    get_current_theme,
    get_theme_base_dir,
    get_theme_base_dirs,
    get_themes
)
from ecommerce.theming.test_utils import with_comprehensive_theme


class TestHelpers(TestCase):
    """
    Test comprehensive theming helper functions.
    """

    def test_get_themes(self):
        """
        Tests get_themes returns all themes in themes directory.
        """
        theme_dirs = get_theme_base_dirs()
        expected_themes = [
            Theme('test-theme', 'test-theme', theme_dirs[0]),
            Theme('test-theme-2', 'test-theme-2', theme_dirs[0]),
            Theme('test-theme-3', 'test-theme-3', theme_dirs[1]),
        ]
        actual_themes = get_themes()
        self.assertCountEqual(expected_themes, actual_themes)

    def test_get_themes_with_theming_disabled(self):
        """
        Tests get_themes returns empty list when theming is disabled.
        """
        with override_settings(ENABLE_COMPREHENSIVE_THEMING=False):
            actual_themes = get_themes()
            self.assertCountEqual([], actual_themes)

    @with_comprehensive_theme('test-theme')
    def test_current_theme_path(self):
        """
        Tests get_current_theme returns Theme with correct directory.
        """
        theme = get_current_theme()
        self.assertEqual(theme.path, settings.DJANGO_ROOT + "/tests/themes/test-theme")
        self.assertIn(theme.path, str(theme))

    @with_comprehensive_theme('test-theme-2')
    def test_current_theme_path_2(self):
        """
        Tests get_current_theme returns Theme with correct directory.
        """
        theme = get_current_theme()
        self.assertEqual(theme.path, settings.DJANGO_ROOT + "/tests/themes/test-theme-2")

    def test_get_current_theme_with_theming_disabled(self):
        """
        Tests get_current_theme returns None if theming is disabled.
        """
        with override_settings(ENABLE_COMPREHENSIVE_THEMING=False):
            theme = get_current_theme()
            self.assertIsNone(theme)

    def test_improperly_configured_error(self):
        """
        Tests ImproperlyConfigured error is raised when COMPREHENSIVE_THEME_DIRS is not a string.
        """
        with override_settings(COMPREHENSIVE_THEME_DIRS=[None]):
            with self.assertRaises(ImproperlyConfigured):
                get_theme_base_dirs()

        # Test that COMPREHENSIVE_THEME_DIRS must be list
        with override_settings(COMPREHENSIVE_THEME_DIRS=''):
            with self.assertRaises(ImproperlyConfigured):
                get_theme_base_dirs()
        # Test that COMPREHENSIVE_THEME_DIRS must be list
        with override_settings(COMPREHENSIVE_THEME_DIRS=None):
            with self.assertRaises(ImproperlyConfigured):
                get_theme_base_dirs()
        # Test that COMPREHENSIVE_THEME_DIRS must be list
        with override_settings(COMPREHENSIVE_THEME_DIRS="ecommerce/tests/themes/tes-theme"):
            with self.assertRaises(ImproperlyConfigured):
                get_theme_base_dirs()

    def test_improperly_configured_error_for_invalid_dir(self):
        """
        Tests ImproperlyConfigured error is raised when COMPREHENSIVE_THEME_DIRS is not an existent path.
        """
        with override_settings(COMPREHENSIVE_THEME_DIRS=["/path/to/non/existent/dir"]):
            with self.assertRaises(ImproperlyConfigured):
                get_theme_base_dirs()

    def test_improperly_configured_error_for_relative_paths(self):
        """
        Tests ImproperlyConfigured error is raised when COMPREHENSIVE_THEME_DIRS is not an existent path.
        """
        with override_settings(COMPREHENSIVE_THEME_DIRS=["ecommerce/tests/themes/tes-theme"]):
            with self.assertRaises(ImproperlyConfigured):
                get_theme_base_dirs()

    @with_comprehensive_theme('test-theme')
    def test_get_current_theme(self):
        """
        Tests current site theme name.
        """
        theme = get_current_theme()
        self.assertEqual(theme.theme_dir_name, 'test-theme')

    def test_get_current_site_theme_raises_no_error_when_accessed_in_commands(self):
        """
        Tests current site theme returns None and does not errors out if it is accessed inside management commands
        and request object is not present.
        """
        with patch("ecommerce.theming.helpers.get_current_request", return_value=None):
            theme = get_current_theme()
            self.assertIsNone(theme)

    @with_comprehensive_theme('test-theme')
    def test_get_current_site_theme_with_theming_disabled(self):
        """
        Tests current site theme returns None when theming is disabled.
        """
        with override_settings(ENABLE_COMPREHENSIVE_THEMING=False):
            theme = get_current_site_theme()
            self.assertIsNone(theme)

    @with_comprehensive_theme('non-existing-theme')
    def test_get_current_theme_value_error(self):
        """
        Tests get current theme method returns None if the theme dir is not present in any of the theme dirs.
        """
        theme = get_current_theme()
        self.assertIsNone(theme)

    @with_comprehensive_theme('test-theme')
    def test_get_current_theme_template_dirs(self):
        """
        Tests get_current_theme().template_dirs returns correct template dirs for the current theme.
        """
        themes_dir = settings.COMPREHENSIVE_THEME_DIRS[0]

        expected_theme_dirs = [
            themes_dir / "test-theme" / "templates",
            themes_dir / "test-theme" / "templates" / "oscar",
        ]
        actual_theme_dirs = get_current_theme().template_dirs
        self.assertCountEqual(expected_theme_dirs, actual_theme_dirs)

    def test_get_all_theme_template_dirs(self):
        """
        Tests get_all_theme_template_dirs returns correct template dirs for all the themes.
        """
        themes_dirs = settings.COMPREHENSIVE_THEME_DIRS

        expected_theme_dirs = [
            themes_dirs[0] / "test-theme" / "templates",
            themes_dirs[0] / "test-theme" / "templates" / "oscar",
            themes_dirs[0] / "test-theme-2" / "templates",
            themes_dirs[0] / "test-theme-2" / "templates" / "oscar",
            themes_dirs[1] / "test-theme-3" / "templates",
            themes_dirs[1] / "test-theme-3" / "templates" / "oscar",
        ]
        actual_theme_dirs = get_all_theme_template_dirs()
        self.assertCountEqual(expected_theme_dirs, actual_theme_dirs)

    def test_get_theme_base_dir(self):
        """
        Tests get_theme_base_dir returns correct directory for a theme.
        """
        theme_dirs = settings.COMPREHENSIVE_THEME_DIRS

        self.assertEqual(get_theme_base_dir("test-theme"), theme_dirs[0])
        self.assertEqual(get_theme_base_dir("test-theme-2"), theme_dirs[0])
        self.assertEqual(get_theme_base_dir("test-theme-3"), theme_dirs[1])

    def test_get_theme_base_dir_error(self):
        """
        Tests get_theme_base_dir raises value error if theme is not found in themes dir.
        """
        with self.assertRaises(ValueError):
            get_theme_base_dir("non-existent-theme")

    def test_get_theme_base_dir_suppress_error(self):
        """
        Tests get_theme_base_dir returns None if theme is not found istead of raising an error.
        """
        self.assertIsNone(get_theme_base_dir("non-existent-theme", suppress_error=True))
