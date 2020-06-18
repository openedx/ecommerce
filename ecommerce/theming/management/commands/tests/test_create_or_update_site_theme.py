"""
Tests for management command for creating or updating site themes.
"""


from django.contrib.sites.models import Site
from django.core.management import CommandError, call_command

from ecommerce.tests.testcases import TestCase
from ecommerce.theming.models import SiteTheme


class TestCreateUpdateSiteTheme(TestCase):
    """
    Test django management command for creating or updating site themes.
    """
    def test_errors_for_invalid_arguments(self):
        """
        Test Error in case of invalid arguments.
        """
        # make sure error is raised if no argument is given
        with self.assertRaises(CommandError):
            call_command("create_or_update_site_theme")

        # make sure error is raised if --site-theme is not given
        with self.assertRaises(CommandError):
            call_command("create_or_update_site_theme", site_domain="test.localhost")

    def test_create_site_theme(self):
        """
        Test that site theme is created properly.
        """
        call_command(
            "create_or_update_site_theme",
            "--site-domain=test.localhost",
            "--site-name=Site Name",
            '--site-theme=test',
        )

        # Verify updated site name
        site = Site.objects.get(domain="test.localhost")
        site_theme = SiteTheme.objects.get(site=site)

        self.assertEqual(site.name, "Site Name")
        self.assertEqual(site_theme.theme_dir_name, "test")

    def test_update_site(self):
        """
        Test that site is updated properly if site-id belongs to an existing site.
        """
        # Create a site to update
        site = Site.objects.create(domain="test.localhost", name="Test Site")
        call_command(
            "create_or_update_site_theme",
            "--site-id={}".format(site.id),
            "--site-name=updated name",
            "--site-domain=test.localhost",
            '--site-theme=test',
        )

        # Verify updated site name
        site = Site.objects.get(id=site.id)
        self.assertEqual(site.name, "updated name")

    def test_update_site_theme(self):
        """
        Test that site theme is updated properly when site and site theme already exist.
        """
        # Create a site and site theme to update
        site = Site.objects.create(domain="test.localhost", name="Test Site")
        site_theme = SiteTheme.objects.create(site=site, theme_dir_name="site_theme_1")

        call_command(
            "create_or_update_site_theme",
            "--site-domain=test.localhost",
            '--site-theme=site_theme_2',
        )

        # Verify updated site name
        site_theme = SiteTheme.objects.get(id=site_theme.id)
        self.assertEqual(site_theme.theme_dir_name, "site_theme_2")
