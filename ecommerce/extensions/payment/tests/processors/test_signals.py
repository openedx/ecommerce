

from django.conf import settings
from django.urls import reverse
from edx_django_utils.cache import TieredCache
from waffle.models import Switch

from ecommerce.extensions.api.v2.views.payments import PAYMENT_PROCESSOR_CACHE_KEY
from ecommerce.tests.testcases import TestCase


class SignalTests(TestCase):
    def test_invalidate_processor_cache(self):
        """ Verify the payment processor cache is invalidated when payment processor switches are toggled. """
        user = self.create_user()
        self.client.login(username=user.username, password=self.password)

        # Make a call that triggers cache creation
        response = self.client.get(reverse('api:v2:payment:list_processors'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(TieredCache.get_cached_response(PAYMENT_PROCESSOR_CACHE_KEY).is_found)

        # Toggle a switch to trigger cache deletion
        Switch.objects.get_or_create(name=settings.PAYMENT_PROCESSOR_SWITCH_PREFIX + 'dummy')
        self.assertFalse(TieredCache.get_cached_response(PAYMENT_PROCESSOR_CACHE_KEY).is_found)
