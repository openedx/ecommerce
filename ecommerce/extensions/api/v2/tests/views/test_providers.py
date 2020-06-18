

import json

import ddt
import httpretty
from django.urls import reverse
from rest_framework import status

from ecommerce.extensions.api.serializers import ProviderSerializer
from ecommerce.tests.testcases import TestCase


@ddt.ddt
class ProvidersViewSetTest(TestCase):
    path = reverse('api:v2:providers:list_providers')

    def setUp(self):
        super(ProvidersViewSetTest, self).setUp()
        user = self.create_user()
        self.client.login(username=user.username, password=self.password)
        self.provider = 'test-provider'
        self.data = {
            'id': self.provider,
            'display_name': self.provider,
            'url': 'http://example.com/',
            'status_url': 'http://status.example.com/',
            'description': 'Description',
            'enable_integration': False,
            'fulfillment_instructions': '',
            'thumbnail_url': 'http://thumbnail.example.com/',
        }

    def mock_provider_api(self, data=None):
        provider_url = '{lms_url}{provider}/'.format(
            lms_url=self.site.siteconfiguration.build_lms_url('api/credit/v1/providers/'),
            provider=self.provider
        )
        httpretty.register_uri(
            httpretty.GET,
            provider_url,
            body=json.dumps(data if data else self.data),
            content_type='application/json'
        )

    @httpretty.activate
    def test_getting_provider(self):
        """Verify endpoint returns correct provider data."""
        self.mock_access_token_response()
        self.mock_provider_api()
        response = self.client.get('{path}?credit_provider_id={provider}'.format(
            path=self.path, provider=self.provider
        ))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertDictEqual(response.json(), ProviderSerializer(self.data).data)

    @httpretty.activate
    def test_getting_provider_with_many_true(self):
        """Verify endpoint returns correct provider data with many True."""
        data = [self.data, self.data]
        self.mock_access_token_response()
        self.mock_provider_api(data=data)
        response = self.client.get('{path}?credit_provider_id={provider}'.format(
            path=self.path, provider=self.provider
        ))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertListEqual(response.json(), ProviderSerializer(data, many=True).data)

    def test_invalid_provider(self):
        """Verify endpoint response is empty for invalid provider."""
        response = self.client.get('{path}?credit_provider_id={provider}'.format(
            path=self.path, provider='invalid-provider'
        ))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.content.decode('utf-8'), '')
