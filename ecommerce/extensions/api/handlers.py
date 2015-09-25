"""Handler overrides for JWT authentication."""
import jwt

from django.conf import settings
from rest_framework_jwt.settings import api_settings


def jwt_decode_handler(token):
    """Attempt to decode the given token with each of the configured JWT issuers.

    Args:
        token (str): the JWT to decode.

    Returns:
        dict: The JWT's payload.

    Raises:
        InvalidIssuerError: if the provided token does not match a configured JWT
            issuer.
        """
    options = {
        'verify_exp': api_settings.JWT_VERIFY_EXPIRATION,
    }
    for issuer in settings.JWT_ISSUERS:
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

    raise jwt.InvalidIssuerError
