from django.test import TestCase
from django.conf import settings
from django.core.urlresolvers import reverse
from django.contrib.auth import get_user_model


User = get_user_model()


class TestUrls(TestCase):
    USERNAME = 'jmcgill'
    PASSWORD = 'slippin_jimmy'
    PROTECTED_URL_NAME = 'dashboard:index'

    def test_unauthorized_redirection(self):
        """Test that users not authorized to access the Oscar front-end are redirected to the LMS dashboard."""
        User.objects.create_user(self.USERNAME, password=self.PASSWORD)

        # Log in as a user not authorized to view the Oscar front-end (no staff permissions)
        success = self.client.login(username=self.USERNAME, password=self.PASSWORD)
        self.assertTrue(success)

        response = self.client.get(reverse(self.PROTECTED_URL_NAME))
        # Test client can't fetch external URLs, so fetch_redirect_response is set to
        # False to avoid loading the final page
        self.assertRedirects(response, settings.LMS_DASHBOARD_URL, fetch_redirect_response=False)
