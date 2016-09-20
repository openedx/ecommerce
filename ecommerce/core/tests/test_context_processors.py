from threadlocals.threadlocals import get_current_request

from ecommerce.core.context_processors import core
from ecommerce.core.url_utils import get_lms_dashboard_url, get_lms_url
from ecommerce.tests.testcases import TestCase


class CoreContextProcessorTests(TestCase):
    def test_core(self):
        request = get_current_request()
        self.assertDictEqual(
            core(request),
            {
                'lms_base_url': get_lms_url(),
                'lms_dashboard_url': get_lms_dashboard_url(),
                'platform_name': request.site.name,
                'support_url': request.site.siteconfiguration.payment_support_url,
            }
        )
