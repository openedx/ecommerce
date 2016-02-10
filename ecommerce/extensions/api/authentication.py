"""JWT authentication scheme for use with DRF."""
import logging

from django.contrib.auth import get_user_model
import requests
from rest_framework import exceptions
from rest_framework.authentication import get_authorization_header, BaseAuthentication
from rest_framework.status import HTTP_200_OK
from rest_framework_jwt.authentication import JSONWebTokenAuthentication

from ecommerce.core.url_utils import get_oauth2_provider_url

logger = logging.getLogger(__name__)
User = get_user_model()


class JwtAuthentication(JSONWebTokenAuthentication):
    """Get or create the user corresponding to the provided JWT.

    Clients should authenticate themselves by passing a JWT in the Authorization
    HTTP header, prepended with the string 'JWT'.

    At a minimum, the JWT payload must contain a username. If an email address
    is provided in the payload, it will be used to update the retrieved user's
    email address which surfaces in the Oscar management interface.

    Additionally, clients may enclose a 'tracking_context' sub-dictionary in the
    JWT payload.  If present, the service will update itself with the value
    of the tracking_context, and will include its contents when firing tracking
    events to analytics services (if and when configured to do so).

    Example:
        Access an endpoint protected by JWT authentication as follows.

        >>> url = 'http://localhost:8002/api/v2/baskets/'  # Protected by JwtAuthentication
        >>> token = jwt.encode({'username': 'Saul', 'email': 'saul@bettercallsaul.com'}, 'insecure-secret-key')
        >>> headers = {
            'content-type': 'application/json',
            'Authorization': 'JWT ' + token
        }
        >>> data = {'products': [{'sku': 'PAID-SEAT'}], 'checkout': True, 'payment_processor_name': 'paypal'}
        >>> response = requests.post(url, data=json.dumps(data), headers=headers)
        >>> response.status_code
        200
    """

    def authenticate(self, request):
        try:
            return super(JwtAuthentication, self).authenticate(request)
        except Exception as ex:
            # Errors in production do not need to be logged (as they may be noisy),
            # but debug logging can help quickly resolve issues during development.
            logger.debug(ex)
            raise

    def authenticate_credentials(self, payload):
        """Get or create an active user with the username contained in the payload."""
        username = payload.get('username')

        if username is None:
            raise exceptions.AuthenticationFailed('Invalid payload.')
        else:
            try:
                user, __ = User.objects.get_or_create(username=username)
                is_update = False
                for attr in ('full_name', 'email', 'tracking_context'):
                    payload_value = payload.get(attr)

                    if getattr(user, attr) != payload_value and payload_value is not None:
                        setattr(user, attr, payload_value)
                        is_update = True
                if is_update:
                    user.save()
            except:
                msg = 'User retrieval failed.'
                logger.exception(msg)
                raise exceptions.AuthenticationFailed(msg)

        return user


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
