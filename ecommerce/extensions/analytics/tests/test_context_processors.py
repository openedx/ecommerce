

from django.test import RequestFactory

from ecommerce.extensions.analytics.context_processors import analytics
from ecommerce.extensions.analytics.utils import prepare_analytics_data
from ecommerce.tests.testcases import TestCase


class AnalyticsContextProcessorTests(TestCase):
    def test_analytics(self):
        request = RequestFactory().get('/')
        request.user = self.create_user()
        request.site = self.site
        analytics_data = prepare_analytics_data(request.user, request.site.siteconfiguration.segment_key)

        self.assertDictEqual(
            analytics(request),
            {
                'analytics_data': analytics_data,
            }
        )
