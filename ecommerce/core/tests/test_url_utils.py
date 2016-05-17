import mock

from django.conf import settings
from edx_rest_api_client.auth import SuppliedJwtAuth
from edx_rest_api_client.client import EdxRestApiClient

from ecommerce.core.exceptions import MissingRequestError
from ecommerce.core.url_utils import(get_course_catalog_api_client,
                                     get_ecommerce_url, get_lms_url,
                                     get_oauth2_provider_url)
from ecommerce.tests.testcases import TestCase


class UrlUtilityTests(TestCase):
    @mock.patch('ecommerce.core.url_utils.get_current_request', mock.Mock(return_value=None))
    def test_get_ecommerce_url_with_no_current_request(self):
        with self.assertRaises(MissingRequestError):
            get_ecommerce_url()

    @mock.patch('ecommerce.core.url_utils.get_current_request', mock.Mock(return_value=None))
    def test_get_lms_url_with_no_current_request(self):
        with self.assertRaises(MissingRequestError):
            get_lms_url()

    @mock.patch.object(EdxRestApiClient, 'get_oauth_access_token')
    def test_get_course_catalog_api_client(self, mock_method):
        mock_method.return_value = ('auth-token', 'now')
        api = get_course_catalog_api_client(self.site)

        mock_method.assert_called_with('{root}/access_token'.format(root=get_oauth2_provider_url()),
                                       self.site.siteconfiguration.oauth_settings['SOCIAL_AUTH_EDX_OIDC_KEY'],
                                       self.site.siteconfiguration.oauth_settings['SOCIAL_AUTH_EDX_OIDC_SECRET'],
                                       token_type='jwt')
        api_session = api._store['session']  # pylint: disable=protected-access
        self.assertEqual('auth-token', api_session.auth.token)
        self.assertEqual(SuppliedJwtAuth, type(getattr(api_session, 'auth')))
        self.assertEqual(settings.COURSE_CATALOG_API_URL, api._store['base_url'])  # pylint: disable=protected-access
