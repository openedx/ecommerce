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
    secret_keys = settings.JWT_AUTH['JWT_SECRET_KEYS'] or (api_settings.JWT_SECRET_KEY,)

    # TODO (CCB): The usage of multiple issuers complicates matters. We should only have one issuer.
    # Update ecommerce-worker to properly use client credentials, and remove the internal loop. (ECOM-4477)
    for secret_key in secret_keys:
        for issuer in issuers:
            try:
                return jwt.decode(
                    token,
                    secret_key,
                    api_settings.JWT_VERIFY,
                    options=options,
                    leeway=api_settings.JWT_LEEWAY,
                    audience=api_settings.JWT_AUDIENCE,
                    issuer=issuer,
                    algorithms=[api_settings.JWT_ALGORITHM]
                )
            except jwt.InvalidIssuerError:
                # Ignore these errors since we have multiple issuers
                pass
            except jwt.DecodeError:
                # Ignore these errors since we have multiple signing keys
                pass
            except jwt.InvalidTokenError:
                logger.exception('JWT decode failed!')

    raise jwt.InvalidTokenError('All combinations of JWT issuers and secret keys failed to validate the token.')
