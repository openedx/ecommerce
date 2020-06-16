"""
Tests for comprehensive theme style, template overrides.
"""


from django.conf import settings
from django.contrib import staticfiles
from django.core.management import call_command
from django.test import override_settings

from ecommerce.tests.testcases import TestCase
from ecommerce.theming.test_utils import compile_sass


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

        # Compress test theme templates
        call_command("compress")

        super(TestComprehensiveTheme, cls).setUpClass()

    def test_templates(self):
        """
        Test that theme template overrides are applied.
        """
        resp = self.client.get('/dashboard/')
        self.assertEqual(resp.status_code, 200)
        # This string comes from header.html of test-theme
        self.assertContains(resp, "This is a Test Theme.")

    def test_logo_image(self):
        """
        Test that theme logo is used instead of default logo.
        """
        themes_dir = settings.COMPREHENSIVE_THEME_DIRS[0]

        result = staticfiles.finders.find('test-theme/images/default-logo.png')
        self.assertEqual(result, themes_dir / "test-theme" / 'static/images/default-logo.png')

    def test_css_files(self):
        """
        Test that theme sass files are used instead of default sass files.
        """
        themes_dir = settings.COMPREHENSIVE_THEME_DIRS[0]

        result = staticfiles.finders.find('test-theme/css/base/main.css')
        self.assertEqual(result, themes_dir / "test-theme" / "static/css/base/main.css")

        main_css = ""
        with open(result) as css_file:
            main_css += css_file.read()

        self.assertIn("background-color: #00fa00", main_css)

    def test_default_theme(self):
        """
        Test that theme template overrides are applied.
        """
        with override_settings(DEFAULT_SITE_THEME="test-theme-2"):
            resp = self.client.get('/dashboard/')
            self.assertEqual(resp.status_code, 200)
            # This string comes from header.html of test-theme
            self.assertContains(resp, "This is second Test Theme.")
