from django.test import override_settings, RequestFactory

from ecommerce.core.context_processors import core
from ecommerce.tests.testcases import TestCase

PLATFORM_NAME = 'Test Platform'


class CoreContextProcessorTests(TestCase):
    @override_settings(PLATFORM_NAME=PLATFORM_NAME)
    def test_core(self):
        request = RequestFactory().get('/')
        self.assertDictEqual(core(request), {'platform_name': PLATFORM_NAME})
