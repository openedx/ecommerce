"""Handler overrides for JWT authentication."""
import logging

import jwt
import waffle
from django.conf import settings
from edx_django_utils import monitoring as monitoring_utils
from edx_rest_framework_extensions.auth.jwt.decoder import jwt_decode_handler as edx_drf_extensions_jwt_decode_handler
from rest_framework_jwt.settings import api_settings

logger = logging.getLogger(__name__)

JWT_DECODE_HANDLER_METRIC_KEY = 'ecom_jwt_decode_handler'


def _ecommerce_jwt_decode_handler_updated_configs(token):
    """
    Same as original with minor modifications to expect
    configuration format matching the expectations of
    edx-drf-extensions decoder.

      JWT_AUTH:
        JWT_ISSUERS:
          - AUDIENCE: '{{ COMMON_JWT_AUDIENCE }}'
            ISSUER: '{{ COMMON_JWT_ISSUER }}'
            SECRET_KEY: '{{ COMMON_JWT_SECRET_KEY }}'

    """
    options = {
        'verify_exp': api_settings.JWT_VERIFY_EXPIRATION,
        'verify_aud': settings.JWT_AUTH['JWT_VERIFY_AUDIENCE'],
    }

    # JWT_ISSUERS is not one of DRF-JWT's default settings, and cannot be accessed
    # using the `api_settings` object without overriding DRF-JWT's defaults.
    issuers = settings.JWT_AUTH['JWT_ISSUERS']

    # Unlike the original two secret-key/issuer loops, here we have a single
    # loop because the secret key is now part of the issuer config.
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
            pass
        except jwt.DecodeError:
            # Ignore these errors since we have multiple issuers
            pass
        except jwt.InvalidTokenError:
            logger.exception('Custom config JWT decode failed!')

    raise jwt.InvalidTokenError('All combinations of JWT issuers with updated config failed to validate the token.')


def _ecommerce_jwt_decode_handler_original(token):
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
                logger.exception('Original JWT decode failed!')

    raise jwt.InvalidTokenError('All combinations of JWT issuers and secret keys failed to validate the token.')


def jwt_decode_handler(token):
    """Attempt to decode the given token with each of the configured JWT issuers.

    Args:
        token (str): The JWT to decode.

    Returns:
        dict: The JWT's payload.

    Raises:
        InvalidTokenError: If the token is invalid, or if none of the
            configured issuer/secret-key combos can properly decode the token.

    """

    # The following versions of decoding are part of a larger rollout plan that
    # will ultimately end in retiring this ecommerce jwt_decode_handler
    # altogether.  See ARCH-261 for detailed plan.

    # first, try jwt_decode_handler from edx_drf_extensions
    try:
        jwt_payload = edx_drf_extensions_jwt_decode_handler(token)
        monitoring_utils.set_custom_metric(JWT_DECODE_HANDLER_METRIC_KEY, 'edx-drf-extensions')
        return jwt_payload
    except Exception:  # pylint: disable=broad-except
        # continue and try again
        if waffle.switch_is_active('jwt_decode_handler.log_exception.edx-drf-extensions'):
            logger.info('Failed to use edx-drf-extensions jwt_decode_handler.', exc_info=True)

    # next, try temporary ecommerce decoder which matches expected config
    # format of edx-drf-extensions
    try:
        jwt_payload = _ecommerce_jwt_decode_handler_updated_configs(token)
        monitoring_utils.set_custom_metric(JWT_DECODE_HANDLER_METRIC_KEY, 'ecommerce-updated-config')
        return jwt_payload
    except Exception:  # pylint: disable=broad-except
        # continue and try again
        if waffle.switch_is_active('jwt_decode_handler.log_exception.ecommerce-updated-config'):
            logger.info('Failed to use custom jwt_decode_handler with updated configs.', exc_info=True)

    # if all else fails, fallback to the original version
    try:
        jwt_payload = _ecommerce_jwt_decode_handler_original(token)
        monitoring_utils.set_custom_metric(JWT_DECODE_HANDLER_METRIC_KEY, 'ecommerce-original')
        return jwt_payload
    except Exception:  # pylint: disable=broad-except
        if waffle.switch_is_active('jwt_decode_handler.log_exception.ecommerce-original'):
            logger.info('Failed to use original jwt_decode_handler.', exc_info=True)
        raise
