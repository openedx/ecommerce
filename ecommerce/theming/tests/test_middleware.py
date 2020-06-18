"""
Tests for theming middleware.
"""
from django.urls import reverse

from ecommerce.tests.testcases import TestCase


class TestPreviewTheme(TestCase):
    """
    Test preview-theme and clear-theme parameters work as expected.
    """

    def setUp(self):
        """
        Clear static file finders cache and register cleanup methods.
        """
        super(TestPreviewTheme, self).setUp()
        self.dashboard_index_url = reverse('dashboard:index')

        # create a user and log in
        self.user = self.create_user(is_staff=True)
        self.client.login(username=self.user.username, password=self.password)

    def tearDown(self):
        # clear any theme overrides
        self.client.get(self.dashboard_index_url + '?clear-theme')

    def test_templates(self):
        """
        Test templates are overridden with preview theme.
        """
        # Test default theme without preview theme parameters
        self.assertContains(
            self.client.get(self.dashboard_index_url),
            "This is a Test Theme.",
        )

        # Test test-theme-2 overrides via preview-theme
        self.assertContains(
            self.client.get(self.dashboard_index_url + '?preview-theme=test-theme-2'),
            "This is second Test Theme.",
        )

        # make sure once theme is accessed via preview-theme, it is stored in session data
        self.assertContains(
            self.client.get(self.dashboard_index_url),
            "This is second Test Theme.",
        )

        # test that clear-theme parameter clears any theme applied via preview-theme
        # In this case once preview theme is cleared, we should be back to default theme
        self.assertContains(
            self.client.get(self.dashboard_index_url + '?clear-theme'),
            "This is a Test Theme.",
        )

        # Verify that theme clearing is persisted in the user's session.
        self.assertContains(
            self.client.get(self.dashboard_index_url),
            "This is a Test Theme.",
        )

        # Test test-theme-3 overrides via preview-theme
        self.assertContains(
            self.client.get(self.dashboard_index_url + '?preview-theme=test-theme-3'),
            "This is third Test Theme in a separate theme directory.",
        )

        # Test test-theme-2 overrides via preview-theme
        self.assertContains(
            self.client.get(self.dashboard_index_url + '?preview-theme=test-theme-2'),
            "This is second Test Theme.",
        )

        # make sure there is no error if theme specified by preview-theme parameter does not exist.
        # If given theme does not exist then open source theme will be used not the default theme.
        self.assertContains(
            self.client.get(self.dashboard_index_url + '?preview-theme=test-theme-non-existent'),
            "Dashboard",
        )
