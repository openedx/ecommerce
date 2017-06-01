from django.core.urlresolvers import reverse

from ecommerce.tests.testcases import TestCase


class TestUrls(TestCase):
    def test_unauthorized_redirection(self):
        """Test that users not authorized to access the Oscar front-end are redirected to the LMS dashboard."""
        user = self.create_user()

        # Log in as a user not authorized to view the Oscar front-end (no staff permissions)
        success = self.client.login(username=user.username, password=self.password)
        self.assertTrue(success)

        response = self.client.get(reverse('dashboard:index'))
        # Test client can't fetch external URLs, so fetch_redirect_response is set to
        # False to avoid loading the final page
        self.assertRedirects(response,self.site_configuration.student_dashboard_url, fetch_redirect_response=False)
