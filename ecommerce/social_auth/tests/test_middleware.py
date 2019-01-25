"""
Tests for social auth middleware
"""

from django.test.client import RequestFactory
from django.test.utils import override_settings
from django.urls import reverse
from social_core.exceptions import AuthStateMissing
from testfixtures import LogCapture

from ecommerce.social_auth.middleware import ExceptionMiddleware
from ecommerce.tests.testcases import TestCase


class SocialAuthMiddlewareTests(TestCase):
    """Tests that ExceptionMiddleware is correctly redirected"""

    def setUp(self):
        self.request = RequestFactory().get("dummy_url")
        self.request.path = reverse('social:complete', args=['edx-oidc'])

    @override_settings(SOCIAL_AUTH_EDX_OIDC_LOGOUT_URL='example.com/logout')
    def test_auth_state_missing_exception_lms_redirection(self):
        """
        Test ExceptionMiddleware is correctly redirected to lms
        logout page when PSA raises AuthStateMissing exception with
        SOCIAL_AUTH_EDX_OIDC_LOGOUT_URL correctly set.
        """

        logger_name = 'ecommerce.social_auth.middleware'
        with LogCapture(logger_name) as l:
            response = ExceptionMiddleware().process_exception(
                self.request, AuthStateMissing('test-backend')
            )
            target_url = response.url

            self.assertEqual(response.status_code, 302)
            self.assertTrue(target_url.endswith('/logout'))

            l.check(
                (logger_name, 'INFO', 'AuthStateMissing exception, redirecting learner to lms logout url.')
            )

    @override_settings(SOCIAL_AUTH_EDX_OIDC_LOGOUT_URL=None)
    def test_auth_state_missing_exception_ecom_redirection(self):
        """
        Test ExceptionMiddleware is correctly redirected to ecommerce
        / page when PSA raises AuthStateMissing exception and finds
        SOCIAL_AUTH_EDX_OIDC_LOGOUT_URL not set.
        """

        logger_name = 'ecommerce.social_auth.middleware'
        with LogCapture(logger_name) as l:
            response = ExceptionMiddleware().process_exception(
                self.request, AuthStateMissing('test-backend')
            )
            target_url = response.url

            self.assertEqual(response.status_code, 302)
            self.assertTrue(target_url.endswith('/'))
            l.check(
                (logger_name, 'INFO', 'AuthStateMissing exception, redirecting learner to ecommerce index page.')
            )
