"""Handler overrides for JWT authentication."""
import logging

import jwt
from django.conf import settings
from rest_framework_jwt.settings import api_settings

logger = logging.getLogger(__name__)


def jwt_decode_handler(token):
    """Attempt to decode the given token with each of the configured JWT issuers.

    Args:
        token (str): The JWT to decode.

    Returns:
        dict: The JWT's payload.

    Raises:
        InvalidIssuerError: If the issuer claim in the provided token does not match
            any configured JWT issuers.
        """
    options = {
        'verify_exp': api_settings.JWT_VERIFY_EXPIRATION,
        'verify_aud': settings.JWT_AUTH['JWT_VERIFY_AUDIENCE'],
    }

    # JWT_ISSUERS is not one of DRF-JWT's default settings, and cannot be accessed
    # using the `api_settings` object without overriding DRF-JWT's defaults.
    issuers = settings.JWT_AUTH['JWT_ISSUERS']
    for issuer in issuers:
        try:
            return jwt.decode(
                token,
                api_settings.JWT_SECRET_KEY,
                api_settings.JWT_VERIFY,
                options=options,
                leeway=api_settings.JWT_LEEWAY,
                audience=api_settings.JWT_AUDIENCE,
                issuer=issuer,
                algorithms=[api_settings.JWT_ALGORITHM]
            )
        except jwt.InvalidIssuerError:
            pass
        except jwt.InvalidTokenError:
            logger.exception('JWT decode failed!')
            raise

    raise jwt.InvalidIssuerError
