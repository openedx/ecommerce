from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase, RequestFactory

from ecommerce.tests.mixins import UserMixin
from ecommerce.core.context_processors import get_settings


class ContextProcessorTests(UserMixin, TestCase):

    def test_get_settings(self):
        """ Verify that the correct settings are returned from the processor. """

        user = self.create_user()

        request = RequestFactory().get('/')
        request.user = user

        actual = get_settings(request)
        expected = {
            'username': user.username,
            'lms_dashboard_url': settings.LMS_DASHBOARD_URL
        }

        self.assertDictEqual(expected, actual)

        request.user = AnonymousUser()
        actual = get_settings(request)
        expected['username'] = None
        self.assertDictEqual(expected, actual)
