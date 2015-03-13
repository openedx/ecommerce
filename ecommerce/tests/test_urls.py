from django.test import TestCase
from django.conf import settings
from django.core.urlresolvers import reverse
from django.contrib.auth import get_user_model
from rest_framework import status


User = get_user_model()


class TestUrls(TestCase):
    USERNAME = 'jmcgill'
    PASSWORD = 'slippin_jimmy'
    PROTECTED_URL_NAME = 'dashboard:index'

    def test_unauthorized_redirection(self):
        """Test that users not authorized to access the Oscar front-end are redirected to the LMS dashboard."""
        User.objects.create_user(self.USERNAME, password=self.PASSWORD)
        success = self.client.login(username=self.USERNAME, password=self.PASSWORD)
        # Verify that login was successful
        self.assertTrue(success)
        
        # Verify that `handler403` returns an `HttpResponseRedirect` with status code 302
        response = self.client.get(reverse(self.PROTECTED_URL_NAME))
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        # See: https://docs.djangoproject.com/en/1.7/ref/request-response/#django.http.HttpResponseRedirect.url
        self.assertEqual(response.url, settings.LMS_DASHBOARD_URL)
