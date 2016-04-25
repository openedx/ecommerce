"""
Tests for comprehensive theme style, template overrides.
"""
from django.conf import settings
from django.test import override_settings
from django.contrib import staticfiles
from django.core.management import call_command
from path import Path

from ecommerce.tests.testcases import TestCase
from ecommerce.theming.test_utils import with_comprehensive_theme


class TestComprehensiveTheme(TestCase):
    """
    Test html, sass and static file overrides for comprehensive themes.
    """

    def setUp(self):
        """
        Clear static file finders cache and register cleanup methods.
        """
        super(TestComprehensiveTheme, self).setUp()

        # Clear the internal staticfiles caches, to get test isolation.
        staticfiles.finders.get_finder.cache_clear()

        # create a user and log in
        self.user = self.create_user(is_staff=True)
        self.client.login(username=self.user.username, password=self.password)

    @classmethod
    def setUpClass(cls):
        """
        Enable Comprehensive theme and compile sass files.
        """
        # compile sass assets for test themes.
        compile_sass()

        super(TestComprehensiveTheme, cls).setUpClass()

    @with_comprehensive_theme("test-theme")
    def test_templates(self):
        """
        Test that theme template overrides are applied.
        """
        with override_settings(COMPRESS_OFFLINE=False, COMPRESS_ENABLED=False):
            resp = self.client.get('/dashboard/')
            self.assertEqual(resp.status_code, 200)
            # This string comes from header.html of test-theme
            self.assertContains(resp, "This is a Test Theme.")

    def test_logo_image(self):
        """
        Test that theme logo is used instead of default logo.
        """
        themes_dir = Path(settings.COMPREHENSIVE_THEME_DIR)

        result = staticfiles.finders.find('test-theme/images/default-logo.png')
        self.assertEqual(result, themes_dir / "test-theme" / 'static/images/default-logo.png')

    def test_css_files(self):
        """
        Test that theme sass files are used instead of default sass files.
        """
        themes_dir = Path(settings.COMPREHENSIVE_THEME_DIR)

        result = staticfiles.finders.find('test-theme/css/base/main.css')
        self.assertEqual(result, themes_dir / "test-theme" / "static/css/base/main.css")

        main_css = ""
        with open(result) as css_file:
            main_css += css_file.read()

        self.assertIn("background-color: #00fa00", main_css)


def compile_sass():
    """
    Call update assets command to compile system and theme sass.
    """
    with override_settings(DEBUG=True):
        # Compile system and theme sass files
        call_command('update_assets')
