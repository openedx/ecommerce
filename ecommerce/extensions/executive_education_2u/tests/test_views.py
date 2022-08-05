import mock
from django.urls import reverse
from rest_framework import status
from testfixtures import LogCapture

from ecommerce.tests.testcases import TestCase


class ExecutiveEducation2UAPIViewSetTests(TestCase):

    def setUp(self):
        super().setUp()

        self.mock_settings = {
            'GET_SMARTER_OAUTH2_PROVIDER_URL': 'https://provider-url.com',
            'GET_SMARTER_OAUTH2_KEY': 'key',
            'GET_SMARTER_OAUTH2_SECRET': 'secret',
            'GET_SMARTER_API_URL': 'https://api-url.com',
        }
        self.terms_and_policies_url = f"{self.mock_settings['GET_SMARTER_API_URL']}/terms"

        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)

    def tearDown(self):
        super().tearDown()

    @mock.patch('ecommerce.extensions.executive_education_2u.views.GetSmarterEnterpriseApiClient')
    def test_get_terms_and_policies_200(self, mock_geag_client):
        terms_and_policies = {
            'privacyPolicy': 'abcd',
            'websiteTermsOfUse': 'efgh',
        }

        mock_client = mock.MagicMock()
        mock_geag_client.return_value = mock_client
        mock_client.get_terms_and_policies.return_value = terms_and_policies

        path = reverse('executive_education_2u:executive_education_2u-get-terms-and-policies')

        with self.settings(**self.mock_settings):
            response = self.client.get(path)
            self.assertEqual(status.HTTP_200_OK, response.status_code)
            self.assertEqual(response.json(), terms_and_policies)

    @mock.patch('ecommerce.extensions.executive_education_2u.views.GetSmarterEnterpriseApiClient')
    def test_get_terms_and_policies_500(self, mock_geag_client):

        logger_name = 'ecommerce.extensions.executive_education_2u.views'

        mock_client = mock.MagicMock()
        mock_geag_client.return_value = mock_client
        mock_client.get_terms_and_policies.side_effect = Exception()

        with self.settings(**self.mock_settings), LogCapture(logger_name) as logger:
            path = reverse('executive_education_2u:executive_education_2u-get-terms-and-policies')
            response = self.client.get(path)
            self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
            self.assertEqual(response.json(), 'Failed to retrieve terms and policies.')
