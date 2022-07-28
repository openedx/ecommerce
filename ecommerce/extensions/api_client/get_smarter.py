
import datetime
import logging

import pytz
import requests
from django.conf import settings
from edx_django_utils.cache import TieredCache
from oauthlib.oauth2 import BackendApplicationClient
from requests_oauthlib import OAuth2Session

logger = logging.getLogger(__name__)


class GetSmarterEnterpriseApiClient:
    """
    Client to interface with the GetSmarter Enterprise API Gateway(GEAG).
    """

    def __init__(self):
        required_settings = [
            'GET_SMARTER_OAUTH2_KEY',
            'GET_SMARTER_OAUTH2_SECRET',
            'GET_SMARTER_OAUTH2_PROVIDER_URL',
            'GET_SMARTER_API_URL'
        ]

        for setting in required_settings:
            if not getattr(settings, setting, None):
                logger.error('Failed to initialize GetSmarterEnterpriseApiClient, missing %s.', setting)
                raise ValueError('Missing {setting}.')

        self.oauth_client_id = settings.GET_SMARTER_OAUTH2_KEY
        self.oauth_client_secret = settings.GET_SMARTER_OAUTH2_SECRET
        self.oauth_provider_url = settings.GET_SMARTER_OAUTH2_PROVIDER_URL
        self.api_url = settings.GET_SMARTER_API_URL
        self.session = requests.Session()

    @property
    def oauth_token_url(self):
        return self.oauth_provider_url + '/oauth2/token'

    @property
    def access_token_cache_key(self):
        return 'get_smart_enterprise_gateway.access_token.{}'.format(self.oauth_client_id)

    def _get_cached_access_token(self):
        """
        Return the cached access token if it is not expired.
        """
        cached_response = TieredCache.get_cached_response(self.access_token_cache_key)

        if cached_response.is_found:
            cached_value = cached_response.value
            expires_at = cached_value['expires_at']
            if datetime.datetime.now(pytz.utc).timestamp() < expires_at:
                return cached_value['access_token']

        return None

    def _get_access_token(self):
        """
        Return the access token required for making calls to Get Smarter API Gateway.
        """
        cached_token = self._get_cached_access_token()
        if cached_token:
            return cached_token

        try:
            client = BackendApplicationClient(client_id=self.oauth_client_id)
            oauth = OAuth2Session(client=client)
            token_response = oauth.fetch_token(
                token_url=self.oauth_token_url,
                client_secret=self.oauth_client_secret
            )
            TieredCache.set_all_tiers(self.access_token_cache_key, token_response, token_response['expires_in'])
            return token_response['access_token']
        except Exception as ex:  # pylint: disable=broad-except
            logger.exception(ex)
            return None

    def _ensure_authentication(self):
        """
        Add the required headers for authentication.
        """
        headers = {
            'User-Agent': 'Mozilla/5.0',  # GEAG blocks the python-requests user agent for certain requests
            'Authorization': 'Bearer ' + self._get_access_token(),
        }
        self.session.headers.update(headers)

    def get_terms_and_conditions(self):
        """
        Fetch and return the terms and conditions from GEAG.
        """
        url = self.api_url + '/terms'
        self._ensure_authentication()
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def create_allocation(self):
        """
        Create an allocation (enrollment) through GEAG.
        """
        return NotImplementedError()
