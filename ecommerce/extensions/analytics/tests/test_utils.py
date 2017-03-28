import json

from django.contrib.auth.models import AnonymousUser

from ecommerce.extensions.analytics.utils import prepare_analytics_data
from ecommerce.tests.testcases import TestCase


class UtilsTest(TestCase):
    """ Tests for the analytics utils. """

    def test_prepare_analytics_data(self):
        """ Verify the function returns correct analytics data for a logged in user."""
        user = self.create_user(
            first_name='John',
            last_name='Doe',
            email='test@example.com',
            tracking_context={'lms_user_id': '1235123'}
        )
        data = prepare_analytics_data(user, self.site.siteconfiguration.segment_key)
        self.assertDictEqual(json.loads(data), {
            'tracking': {'segmentApplicationId': self.site.siteconfiguration.segment_key},
            'user': {'user_tracking_id': '1235123', 'name': 'John Doe', 'email': 'test@example.com'}
        })

    def test_anon_prepare_analytics_data(self):
        """ Verify the function returns correct analytics data for an anonymous user."""
        user = AnonymousUser()
        data = prepare_analytics_data(user, self.site.siteconfiguration.segment_key)
        self.assertDictEqual(json.loads(data), {
            'tracking': {'segmentApplicationId': self.site.siteconfiguration.segment_key},
            'user': 'AnonymousUser'
        })
