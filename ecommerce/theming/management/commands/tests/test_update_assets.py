"""
Tests for Management commands of comprehensive theming.
"""


from django.conf import settings
from django.core.management import CommandError, call_command
from django.test import override_settings
from mock import Mock, patch
from path import Path

from ecommerce.tests.testcases import TestCase
from ecommerce.theming.helpers import get_themes
from ecommerce.theming.management.commands.update_assets import (
    SYSTEM_SASS_PATHS,
    Command,
    compile_sass,
    get_sass_directories
)


class TestUpdateAssets(TestCase):
    """
    Test management command for updating/compiling themed assets.
    """
    def setUp(self):
        super(TestUpdateAssets, self).setUp()
        self.themes = get_themes()

    def test_errors_for_invalid_arguments(self):
        """
        Test update_asset command.
        """
        # make sure error is raised for invalid theme list
        with self.assertRaises(CommandError):
            call_command("update_assets", themes=["all", "test-theme"])

        # make sure error is raised for invalid theme list
        with self.assertRaises(CommandError):
            call_command("update_assets", themes=["no", "test-theme"])

        # make sure error is raised for invalid theme list
        with self.assertRaises(CommandError):
            call_command("update_assets", themes=["all", "no"])

        # make sure error is raised for invalid theme list
        with self.assertRaises(CommandError):
            call_command("update_assets", themes=["test-theme", "non-existing-theme"])

    def test_parse_arguments(self):
        """
        Test parse arguments method for update_asset command.
        """
        # make sure update_assets picks all themes when called with 'themes=all' option
        parsed_args = Command.parse_arguments(themes=["all"])
        self.assertEqual(parsed_args[0], get_themes())

        # make sure update_assets picks no themes when called with 'themes=no' option
        parsed_args = Command.parse_arguments(themes=["no"])
        self.assertEqual(parsed_args[0], [])

        # make sure update_assets picks only specified themes
        parsed_args = Command.parse_arguments(themes=["test-theme"])
        self.assertEqual(parsed_args[0], [theme for theme in get_themes() if theme.theme_dir_name == "test-theme"])

    def test_skip_theme_sass_when_theming_is_disabled(self):
        """
        Test that theme sass is not compiled when theming is disabled.
        """
        with override_settings(ENABLE_COMPREHENSIVE_THEMING=False):
            with patch(
                    "ecommerce.theming.management.commands.update_assets.get_sass_directories") as mock_get_sass_dirs:

                # make sure update_assets skip theme sass if theming is disabled eben if called with 'themes=all'
                call_command("update_assets", "--skip-collect", themes=["all"])
                mock_get_sass_dirs.assert_called_once_with([], True)

    def test_get_sass_directories(self):
        """
        Test that proper sass dirs are returned by get_sass_directories
        """
        themes_dirs = settings.COMPREHENSIVE_THEME_DIRS

        expected_directories = [
            {
                "sass_source_dir": Path("ecommerce/static/sass/base"),
                "css_destination_dir": Path("ecommerce/static/css/base"),
                "lookup_paths": SYSTEM_SASS_PATHS,
            },
            {
                "sass_source_dir": Path("ecommerce/static/sass/base"),
                "css_destination_dir": themes_dirs[0] / "test-theme" / "static" / "css" / "base",
                "lookup_paths": [themes_dirs[0] / "test-theme" / "static" / "sass" / "partials"] + SYSTEM_SASS_PATHS,
            },
            {
                "sass_source_dir": Path("ecommerce/static/sass/base"),
                "css_destination_dir": themes_dirs[0] / "test-theme-2" / "static" / "css" / "base",
                "lookup_paths": [themes_dirs[0] / "test-theme-2" / "static" / "sass" / "partials"] + SYSTEM_SASS_PATHS,
            },
            {
                "sass_source_dir": themes_dirs[0] / "test-theme-2" / "static" / "sass" / "base",
                "css_destination_dir": themes_dirs[0] / "test-theme-2" / "static" / "css" / "base",
                "lookup_paths": [themes_dirs[0] / "test-theme-2" / "static" / "sass" / "partials"] + SYSTEM_SASS_PATHS,
            },
            {
                "sass_source_dir": Path("ecommerce/static/sass/base"),
                "css_destination_dir": themes_dirs[1] / "test-theme-3" / "static" / "css" / "base",
                "lookup_paths": [themes_dirs[1] / "test-theme-3" / "static" / "sass" / "partials"] + SYSTEM_SASS_PATHS,
            },
        ]

        returned_dirs = get_sass_directories(themes=self.themes, system=True)
        self.assertCountEqual(expected_directories, returned_dirs)

    def test_get_sass_directories_with_no_themes(self):
        """
        Test that get_sass_directories returns only system sass directories when called
        with empty list of themes and system=True
        """
        expected_directories = [
            {
                "sass_source_dir": Path("ecommerce/static/sass/base"),
                "css_destination_dir": Path("ecommerce/static/css/base"),
                "lookup_paths": SYSTEM_SASS_PATHS,
            }
        ]

        returned_dirs = get_sass_directories(themes=[], system=True)
        self.assertCountEqual(expected_directories, returned_dirs)

    def test_non_existent_sass_dir_error(self):
        """
        Test ValueError is raised if sass directory provided to the compile_sass method does not exist.
        """
        themes_dir = settings.COMPREHENSIVE_THEME_DIRS[0]

        with self.assertRaises(ValueError):
            compile_sass(
                sass_source_dir=themes_dir / "test-theme" / "sass" / "non-existent",
                css_destination_dir=themes_dir / "test-theme" / "static" / "css" / "base",
                lookup_paths=[themes_dir / "test-theme" / "static" / "sass" / "partials"] + SYSTEM_SASS_PATHS
            )

    def test_collect_static(self):
        """
        Test that collect status is called when update_assets is called in production mode (i.e. DEBUG=False).
        """
        with patch("ecommerce.theming.management.commands.update_assets.call_command", Mock()) as mock_call_command:
            call_command("update_assets", "--skip-system", themes=[])

            self.assertTrue(mock_call_command.called)
            mock_call_command.assert_called_with("collectstatic")

    def test_skip_collect(self):
        """
        Test that call to collect status is skipped when --skip-collect is passed to update_assets command.
        """
        with patch("ecommerce.theming.management.commands.update_assets.call_command", Mock()) as mock_call_command:
            call_command("update_assets", "--skip-collect", "--skip-system", themes=[])

            self.assertFalse(mock_call_command.called)
