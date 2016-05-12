"""JWT authentication scheme for use with DRF."""
import logging

import requests
from django.contrib.auth import get_user_model
from rest_framework import exceptions
from rest_framework.authentication import get_authorization_header, BaseAuthentication
from rest_framework.status import HTTP_200_OK

from ecommerce.core.url_utils import get_oauth2_provider_url

logger = logging.getLogger(__name__)
User = get_user_model()


class BearerAuthentication(BaseAuthentication):
    """
    Simple token based authentication.

    Clients should authenticate by passing the token key in the "Authorization"
    HTTP header, prepended with the string "Bearer ".  For example:

        Authorization: Bearer 401f7ac837da42b97f613d789819ff93537bee6a
    """

    def authenticate(self, request):
        provider_url = get_oauth2_provider_url()
        if not provider_url:
            return None

        provider_url = provider_url.strip('/')

        auth = get_authorization_header(request).split()

        if not auth or auth[0].lower() != b'bearer':
            return None

        if len(auth) == 1:
            raise exceptions.AuthenticationFailed('Invalid token header. No credentials provided.')
        elif len(auth) > 2:
            raise exceptions.AuthenticationFailed('Invalid token header. Token string should not contain spaces.')

        return self.authenticate_credentials(provider_url, auth[1])

    def authenticate_credentials(self, provider_url, key):
        try:
            response = requests.get('{}/access_token/{}/'.format(provider_url, key))
            if response.status_code != HTTP_200_OK:
                raise exceptions.AuthenticationFailed('Invalid token.')

            data = response.json()
            user = User.objects.get(username=data['username'])
        except User.DoesNotExist:
            raise exceptions.AuthenticationFailed('Invalid token.')

        if not user.is_active:
            raise exceptions.AuthenticationFailed('User inactive or deleted.')

        return user, key

    def authenticate_header(self, request):
        return 'Bearer'
