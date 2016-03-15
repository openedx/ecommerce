from django.test import override_settings, RequestFactory

from ecommerce.core.context_processors import core
from ecommerce.core.url_utils import get_lms_dashboard_url
from ecommerce.tests.testcases import TestCase

PLATFORM_NAME = 'Test Platform'
SUPPORT_URL = 'example.com'


class CoreContextProcessorTests(TestCase):
    @override_settings(PLATFORM_NAME=PLATFORM_NAME, SUPPORT_URL=SUPPORT_URL)
    def test_core(self):
        request = RequestFactory().get('/')
        self.assertDictEqual(
            core(request),
            {
                'lms_dashboard_url': get_lms_dashboard_url(),
                'platform_name': PLATFORM_NAME,
                'support_url': SUPPORT_URL
            }
        )
