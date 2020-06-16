"""
Tests for comprehensive theme static files storage classes.
"""


from django.conf import settings
from django.test import override_settings
from mock import patch

from ecommerce.tests.testcases import TestCase
from ecommerce.theming.helpers import Theme, get_theme_base_dir
from ecommerce.theming.storage import ThemeStorage


@override_settings(DEBUG=True)
class TestThemeStorage(TestCase):
    """
    Test comprehensive theming static files storage.
    """

    def setUp(self):
        super(TestThemeStorage, self).setUp()
        self.themes_dir = settings.COMPREHENSIVE_THEME_DIRS[0]
        self.enabled_theme = "test-theme"
        self.storage = ThemeStorage(location=self.themes_dir / self.enabled_theme / 'static')

    def test_themed_asset(self):
        """
        Verify storage returns True on themed assets
        """
        asset = "images/default-logo.png"
        self.assertTrue(self.storage.themed(asset, self.enabled_theme))

    @override_settings(DEBUG=True)
    def test_non_themed_asset(self):
        """
        Verify storage returns False on assets that are not themed
        """
        asset = "images/cap.png"
        self.assertFalse(self.storage.themed(asset, self.enabled_theme))

    def test_themed_with_theming_disabled(self):
        """
        Verify storage returns False when theming is disabled even if given asset is themed
        """
        asset = "images/default-logo.png"
        with override_settings(ENABLE_COMPREHENSIVE_THEMING=False):
            self.assertFalse(self.storage.themed(asset, self.enabled_theme))

    def test_themed_missing_theme_name(self):
        """
        Verify storage.themed returns False when theme name is empty or None.
        """
        asset = "images/default-logo.png"
        self.assertFalse(self.storage.themed(asset, ""))
        self.assertFalse(self.storage.themed(asset, None))

    def test_url(self):
        """
        Verify storage returns correct url depending upon the enabled theme
        """
        asset = "images/default-logo.png"
        with patch(
                "ecommerce.theming.storage.get_current_theme",
                return_value=Theme(self.enabled_theme, self.enabled_theme, get_theme_base_dir(self.enabled_theme))):
            asset_url = self.storage.url(asset)
            # remove hash key from file url
            expected_url = self.storage.base_url + self.enabled_theme + "/" + asset

            self.assertEqual(asset_url, expected_url)

    def test_path(self):
        """
        Verify storage returns correct file path depending upon the enabled theme
        """
        asset = "images/default-logo.png"
        with patch(
                "ecommerce.theming.storage.get_current_theme",
                return_value=Theme(self.enabled_theme, self.enabled_theme, get_theme_base_dir(self.enabled_theme))):
            returned_path = self.storage.path(asset)
            expected_path = self.themes_dir / self.enabled_theme / "static" / asset

            self.assertEqual(expected_path, returned_path)
