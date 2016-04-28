"""
Tests of comprehensive theming.
"""
from mock import patch

from django.test import override_settings
from django.conf import settings, ImproperlyConfigured
from django.contrib.sites.models import Site

from path import Path

from ecommerce.tests.testcases import TestCase
from ecommerce.theming.helpers import (
    get_current_site_theme_dir, get_themes, Theme, get_theme_dir, get_current_theme_template_dirs,
    get_all_theme_template_dirs, get_base_themes_dir,
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
        expected_themes = [
            Theme('test-theme', 'test-theme'),
            Theme('test-theme-2', 'test-theme-2'),
        ]
        actual_themes = get_themes()
        self.assertItemsEqual(expected_themes, actual_themes)

    def test_get_themes_with_theming_disabled(self):
        """
        Tests get_themes returns empty list when theming is disabled.
        """
        with override_settings(ENABLE_COMPREHENSIVE_THEMING=False):
            actual_themes = get_themes()
            self.assertItemsEqual([], actual_themes)

    @with_comprehensive_theme('test-theme')
    def test_get_theme_dir(self):
        """
        Tests get_theme_dir returns correct directory.
        """
        theme_dir = get_theme_dir()
        self.assertEqual(theme_dir, settings.DJANGO_ROOT + "/tests/themes/test-theme")

    @with_comprehensive_theme('test-theme-2')
    def test_get_theme_dir_2(self):
        """
        Tests get_theme_dir returns correct directory.
        """
        theme_dir = get_theme_dir()
        self.assertEqual(theme_dir, settings.DJANGO_ROOT + "/tests/themes/test-theme-2")

    def test_get_theme_dir_with_theming_disabled(self):
        """
        Tests get_theme_dir returns None if theming is disabled.
        """
        with override_settings(ENABLE_COMPREHENSIVE_THEMING=False):
            theme_dir = get_theme_dir()
            self.assertIsNone(theme_dir)

    def test_default_site_theme(self):
        """
        Tests get_theme_dir returns DEFAULT_SITE_THEME if theming is enabled and no site theme is present.
        """
        site, __ = Site.objects.get_or_create(domain="test.edx.org", name="test.edx.org")
        with patch('ecommerce.theming.helpers.get_current_site', return_value=site):
            theme_dir = get_theme_dir()
            self.assertEqual(
                settings.DJANGO_ROOT + "/tests/themes/{}".format(settings.DEFAULT_SITE_THEME),
                theme_dir,
            )

    def test_default_current_site_theme_dir(self):
        """
        Tests get_current_site_theme_dir returns DEFAULT_SITE_THEME if theming is enabled and no site theme is present.
        """
        site, __ = Site.objects.get_or_create(domain="test.edx.org", name="test.edx.org")
        with patch('ecommerce.theming.helpers.get_current_site', return_value=site):
            theme_dir = get_current_site_theme_dir()
            self.assertEqual(settings.DEFAULT_SITE_THEME, theme_dir)

    def test_improperly_configured_error(self):
        """
        Tests ImproperlyConfigured error is raised when COMPREHENSIVE_THEME_DIR is not a string.
        """
        with override_settings(COMPREHENSIVE_THEME_DIR=None):
            with self.assertRaises(ImproperlyConfigured):
                get_base_themes_dir()

    def test_improperly_configured_error_for_invalid_dir(self):
        """
        Tests ImproperlyConfigured error is raised when COMPREHENSIVE_THEME_DIR is not an existent path.
        """
        with override_settings(COMPREHENSIVE_THEME_DIR="/path/to/non/existent/dir"):
            with self.assertRaises(ImproperlyConfigured):
                get_base_themes_dir()

    def test_improperly_configured_error_for_relative_paths(self):
        """
        Tests ImproperlyConfigured error is raised when COMPREHENSIVE_THEME_DIR is not an existent path.
        """
        with override_settings(COMPREHENSIVE_THEME_DIR="ecommerce/tests/themes/tes-theme"):
            with self.assertRaises(ImproperlyConfigured):
                get_base_themes_dir()

    @with_comprehensive_theme('test-theme')
    def test_get_current_site_theme_dir(self):
        """
        Tests current site theme name.
        """
        current_site = get_current_site_theme_dir()
        self.assertEqual(current_site, 'test-theme')

    def test_get_current_site_theme_raises_no_error_when_accessed_in_commands(self):
        """
        Tests current site theme returns None and does not errors out if it is accessed inside management commands
        and request object is not present.
        """
        with patch("ecommerce.theming.helpers.get_current_request", return_value=None):
            current_site = get_current_site_theme_dir()
            self.assertIsNone(current_site)

    @with_comprehensive_theme('test-theme')
    def test_get_current_theme_template_dirs(self):
        """
        Tests get_current_theme_template_dirs returns correct template dirs for the current theme.
        """
        themes_dir = Path(settings.COMPREHENSIVE_THEME_DIR)

        expected_theme_dirs = [
            themes_dir / "test-theme" / "templates",
            themes_dir / "test-theme" / "templates" / "oscar",
        ]
        actual_theme_dirs = get_current_theme_template_dirs()
        self.assertItemsEqual(expected_theme_dirs, actual_theme_dirs)

    def test_get_all_theme_template_dirs(self):
        """
        Tests get_all_theme_template_dirs returns correct template dirs for all the themes.
        """
        themes_dir = Path(settings.COMPREHENSIVE_THEME_DIR)

        expected_theme_dirs = [
            themes_dir / "test-theme" / "templates",
            themes_dir / "test-theme" / "templates" / "oscar",
            themes_dir / "test-theme-2" / "templates",
            themes_dir / "test-theme-2" / "templates" / "oscar",
        ]
        actual_theme_dirs = get_all_theme_template_dirs()
        self.assertItemsEqual(expected_theme_dirs, actual_theme_dirs)
