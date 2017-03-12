import json

from django.core.urlresolvers import reverse

from ecommerce.extensions.api.serializers import SiteConfigurationSerializer
from ecommerce.tests.factories import SiteConfigurationFactory
from ecommerce.tests.testcases import TestCase


class SiteConfigurationViewSetTests(TestCase):
    """Tests for the site configuration API endpoint."""

    def setUp(self):
        super(SiteConfigurationViewSetTests, self).setUp()
        self.site_configuration = SiteConfigurationFactory(
            partner__name='TestX',
            site__domain='test.api.endpoint',
            segment_key='test_segment_key',
            enable_enrollment_codes=True
        )
        self.path = reverse('api:v2:siteconfiguration-list')

        self.user = self.create_user(is_staff=True)
        self.client.login(username=self.user.username, password=self.password)

    def test_authentication_required(self):
        """Test that a guest cannot access the view."""
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)

        self.client.logout()
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 401)

    def test_authorization_required(self):
        """Test that a non-staff user cannot access the view."""
        user = self.create_user(is_staff=False)
        self.client.login(username=user.username, password=self.password)

        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 403)

    def test_site_configuration_response(self):
        """Verify proper site configuration data was returned."""
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        response_content = json.loads(response.content)
        self.assertEqual(response_content['results'][1], SiteConfigurationSerializer(self.site_configuration).data)
