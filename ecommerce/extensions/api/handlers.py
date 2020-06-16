"""
Handler overrides for JWT authentication.

See ARCH-276 for details of removing additional issuers and retiring this
custom jwt_decode_handler.

"""


import logging

import jwt
import waffle
from django.conf import settings
from edx_django_utils import monitoring as monitoring_utils
from edx_rest_framework_extensions.auth.jwt.decoder import jwt_decode_handler as edx_drf_extensions_jwt_decode_handler
from rest_framework_jwt.settings import api_settings

logger = logging.getLogger(__name__)

JWT_DECODE_HANDLER_METRIC_KEY = 'ecom_jwt_decode_handler'


def _ecommerce_jwt_decode_handler_multiple_issuers(token):
    """
    Unlike the edx-drf-extensions jwt_decode_handler implementation, this
    jwt_decode_handler loops over multiple issuers using the same config
    format as the edx-drf-extensions decoder.  Example::

      JWT_AUTH:
        JWT_ISSUERS:
          - AUDIENCE: '{{ COMMON_JWT_AUDIENCE }}'
            ISSUER: '{{ COMMON_JWT_ISSUER }}'
            SECRET_KEY: '{{ COMMON_JWT_SECRET_KEY }}'

    See ARCH-276 for details of removing additional issuers and retiring this
    custom jwt_decode_handler.

    """
    options = {
        'verify_exp': api_settings.JWT_VERIFY_EXPIRATION,
        'verify_aud': settings.JWT_AUTH['JWT_VERIFY_AUDIENCE'],
    }
    error_msg = ''

    # JWT_ISSUERS is not one of DRF-JWT's default settings, and cannot be accessed
    # using the `api_settings` object without overriding DRF-JWT's defaults.
    issuers = settings.JWT_AUTH['JWT_ISSUERS']

    for issuer in issuers:
        try:
            return jwt.decode(
                token,
                issuer['SECRET_KEY'],
                api_settings.JWT_VERIFY,
                options=options,
                leeway=api_settings.JWT_LEEWAY,
                audience=issuer['AUDIENCE'],
                issuer=issuer['ISSUER'],
                algorithms=[api_settings.JWT_ALGORITHM]
            )
        except jwt.InvalidIssuerError:
            # Ignore these errors since we have multiple issuers
            error_msg += "Issuer {} does not match token. ".format(issuer['ISSUER'])
        except jwt.DecodeError:
            # Ignore these errors since we have multiple issuers
            error_msg += "Wrong secret_key for issuer {}. ".format(issuer['ISSUER'])
        except jwt.InvalidAlgorithmError:  # pragma: no cover
            # These should all fail because asymmetric keys are not supported
            error_msg += "Algorithm not supported. "
            break
        except jwt.InvalidTokenError:
            error_msg += "Invalid token found using issuer {}. ".format(issuer['ISSUER'])
            logger.exception('Custom config JWT decode failed!')

    raise jwt.InvalidTokenError(
        'All combinations of JWT issuers with updated config failed to validate the token. ' + error_msg
    )


def jwt_decode_handler(token):
    """
    Attempt to decode the given token with each of the configured JWT issuers.

    Args:
        token (str): The JWT to decode.

    Returns:
        dict: The JWT's payload.

    Raises:
        InvalidTokenError: If the token is invalid, or if none of the
            configured issuer/secret-key combos can properly decode the token.

    """

    # First, try ecommerce decoder that handles multiple issuers.
    # See ARCH-276 for details of removing additional issuers and retiring this
    # custom jwt_decode_handler.
    try:
        jwt_payload = _ecommerce_jwt_decode_handler_multiple_issuers(token)
        monitoring_utils.set_custom_metric(JWT_DECODE_HANDLER_METRIC_KEY, 'ecommerce-multiple-issuers')
        return jwt_payload
    except Exception:  # pylint: disable=broad-except
        if waffle.switch_is_active('jwt_decode_handler.log_exception.ecommerce-multiple-issuers'):
            logger.info('Failed to use ecommerce multiple issuer jwt_decode_handler.', exc_info=True)

    # Next, try jwt_decode_handler from edx_drf_extensions
    # Note: this jwt_decode_handler can handle asymmetric keys, but only a
    #   single issuer. Therefore, the LMS must be the first configured issuer.
    try:
        jwt_payload = edx_drf_extensions_jwt_decode_handler(token)
        monitoring_utils.set_custom_metric(JWT_DECODE_HANDLER_METRIC_KEY, 'edx-drf-extensions')
        return jwt_payload
    except Exception:  # pylint: disable=broad-except
        # continue and try again
        if waffle.switch_is_active('jwt_decode_handler.log_exception.edx-drf-extensions'):
            logger.info('Failed to use edx-drf-extensions jwt_decode_handler.', exc_info=True)
        raise
