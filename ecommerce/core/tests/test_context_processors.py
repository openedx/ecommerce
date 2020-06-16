

from faker import Faker

from ecommerce.core.context_processors import core
from ecommerce.core.url_utils import get_lms_dashboard_url, get_lms_url
from ecommerce.tests.testcases import TestCase


class CoreContextProcessorTests(TestCase):
    def test_core(self):
        site_configuration = self.site.siteconfiguration
        site_configuration.optimizely_snippet_src = Faker().url()
        site_configuration.save()

        self.assertEqual(
            core(self.request),
            {
                'lms_base_url': get_lms_url(),
                'lms_dashboard_url': get_lms_dashboard_url(),
                'platform_name': self.site.name,
                'support_url': site_configuration.payment_support_url,
                'optimizely_snippet_src': site_configuration.optimizely_snippet_src,
            }
        )
