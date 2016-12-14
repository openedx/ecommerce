import json

from django.contrib.auth.models import AnonymousUser

from ecommerce.extensions.analytics.utils import prepare_analytics_data
from ecommerce.tests.testcases import TestCase


class UtilsTest(TestCase):
    """ Tests for the analytics utils. """

    def test_prepare_analytics_data(self):
        """ Verify the function returns correct analytics data for a logged in user."""
        user = self.create_user(
            username='Tester',
            first_name='John',
            last_name='Doe',
            email='test@example.com'
        )
        data = prepare_analytics_data(user, self.site.siteconfiguration, 'a/b/c')
        self.assertDictEqual(json.loads(data), {
            'course': {'courseId': 'a/b/c'},
            'tracking': {
                'googleAnalyticsTrackingIds': self.site.siteconfiguration.google_analytics_tracking_ids,
                'segmentApplicationId': self.site.siteconfiguration.default_segment_key
            },
            'user': {'username': 'Tester', 'name': 'John Doe', 'email': 'test@example.com'}
        })

    def test_anon_prepare_analytics_data(self):
        """ Verify the function returns correct analytics data for an anonymous user."""
        user = AnonymousUser()
        data = prepare_analytics_data(user, self.site.siteconfiguration, 'a/b/c')
        self.assertDictEqual(json.loads(data), {
            'course': {'courseId': 'a/b/c'},
            'tracking': {
                'googleAnalyticsTrackingIds': self.site.siteconfiguration.google_analytics_tracking_ids,
                'segmentApplicationId': self.site.siteconfiguration.default_segment_key
            },
            'user': 'AnonymousUser'
        })
