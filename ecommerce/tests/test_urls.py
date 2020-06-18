

from django.urls import reverse

from ecommerce.core.url_utils import get_lms_dashboard_url
from ecommerce.tests.testcases import TestCase


class TestUrls(TestCase):
    def test_api_docs(self):
        """
        Verify that the API docs render.
        """
        path = reverse('api_docs')
        response = self.client.get(path)

        assert response.status_code == 200

    def test_anonymous_homepage_redirection(self):
        """Test that anonymous users redirected to LMS Dashboard."""
        response = self.client.get('/')
        self.assertRedirects(response, reverse('dashboard:index'), target_status_code=302)

        response = self.client.get(response.url)
        # Anonymous users are further redirected to login page from dashboard
        # After login they will be redirected to respective dashboard as of their authorization
        self.assertRedirects(response, "/dashboard/login/?next=/dashboard/", fetch_redirect_response=False)

    def test_unauthorized_homepage_redirection(self):
        """Test that users unauthorized to access the Oscar front-end are redirected to LMS Dashboard."""
        user = self.create_user()  # unauthorized user cannot view the Oscar Dashboard
        success = self.client.login(username=user.username, password=self.password)
        self.assertTrue(success)
        response = self.client.get('/')

        # Unauthorized users are first redirected to oscar dashboard
        # status code of 302 verifies further redirection on LMS dashboard
        self.assertRedirects(response, reverse('dashboard:index'), target_status_code=302)
        response = self.client.get(response.url)

        # Test client can't fetch external URLs, so fetch_redirect_response is set to
        # False to avoid loading the final page
        self.assertRedirects(response, get_lms_dashboard_url(), fetch_redirect_response=False)

    def test_authorized_homepage_redirection(self):
        """Test that users authorized to access the Oscar front-end are redirected to Oscar Dashboard."""
        user = self.create_user(is_staff=True)  # authorized user to view the Oscar Dashboard
        success = self.client.login(username=user.username, password=self.password)
        self.assertTrue(success)
        response = self.client.get('/')

        # Authorized users are redirected to oscar dashboard
        # status code of 200 verifies that no further redirection on LMS dashboard
        self.assertRedirects(response, reverse('dashboard:index'), target_status_code=200)
