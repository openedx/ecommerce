import json
from datetime import datetime
from unittest import mock

import ddt
import pytz
import responses
from django.test import TestCase

from ecommerce.extensions.api_client.get_smarter import GetSmarterEnterpriseApiClient


@ddt.ddt
class TestGetSmarterEnterpriseApiClient(TestCase):
    def setUp(self):
        super().setUp()

        self.mock_settings = {
            'GET_SMARTER_OAUTH2_PROVIDER_URL': 'https://provider-url.com',
            'GET_SMARTER_OAUTH2_KEY': 'key',
            'GET_SMARTER_OAUTH2_SECRET': 'secret',
            'GET_SMARTER_API_URL': 'https://api-url.com',
        }

    def mock_access_token(
        self,
        token='abcd',
    ):
        responses.add(
            responses.POST,
            self.mock_settings['GET_SMARTER_OAUTH2_PROVIDER_URL'] + '/oauth2/token',
            body=json.dumps({
                'access_token': token,
                'expires_in': 300,
                'expires_at': datetime.now(pytz.utc).timestamp() + 300
            }),
            status=200,
        )

    def test_init_missing_setting(self):
        """
        Test that an error is raise if a required setting is missing.
        """
        with self.settings(**{**self.mock_settings, 'GET_SMARTER_OAUTH2_SECRET': None}):
            self.assertRaises(ValueError, GetSmarterEnterpriseApiClient)

    def test_init_success(self):
        with self.settings(**self.mock_settings):
            client = GetSmarterEnterpriseApiClient()
            self.assertEqual(client.oauth_client_secret, self.mock_settings['GET_SMARTER_OAUTH2_SECRET'])

    @responses.activate
    def test_get_access_token(self):
        """
        Test that the client can get an access token using the credentials in the settings.
        """
        with self.settings(**self.mock_settings):
            self.mock_access_token('abcd')
            client = GetSmarterEnterpriseApiClient()
            access_token = client._get_access_token()
            self.assertEqual(access_token, 'abcd')

    @ddt.data(
        (False, 'bcde'),
        (True, 'abcd'),
    )
    @ddt.unpack
    @mock.patch('ecommerce.extensions.api_client.get_smarter.TieredCache')
    @responses.activate
    def test_cached_access_token(self, is_expired, expected_token, mock_tiered_cache):
        """
        Test that the cached token is used if it's not expired.
        """

        mock_tiered_cache.get_cached_response.return_value = mock.MagicMock(
            value={
                'access_token': 'bcde',
                'expires_in': 60,
                'expires_at': datetime.now(pytz.utc).timestamp() + (-60 if is_expired else 60)
            },
            is_found=True
        )

        with self.settings(**self.mock_settings):
            self.mock_access_token('abcd')
            client = GetSmarterEnterpriseApiClient()
            access_token = client._get_access_token()
            self.assertEqual(access_token, expected_token)

    @responses.activate
    def test_get_terms_and_conditions(self):
        terms_and_conditions = {
            'privacyPolicy': 'abcd',
            'websiteTermsOfUse': 'efgh',
        }

        with self.settings(**self.mock_settings):
            self.mock_access_token('abcd')
            responses.add(
                responses.GET,
                self.mock_settings['GET_SMARTER_API_URL'] + '/terms',
                body=json.dumps(terms_and_conditions),
                status=200,
            )

            client = GetSmarterEnterpriseApiClient()
            response = client.get_terms_and_conditions()
            self.assertEqual(terms_and_conditions, response)
