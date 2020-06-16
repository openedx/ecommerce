

from django.urls import reverse

from ecommerce.tests.testcases import TestCase


class SDNFailureTests(TestCase):
    failure_path = reverse('sdn:failure')

    def test_sdn_logout_context(self):
        """SDN logout view needs to have the logout URL in its context."""
        logout_url = self.site.siteconfiguration.build_lms_url('logout')
        response = self.client.get(self.failure_path)
        self.assertEqual(response.context['logout_url'], logout_url)
