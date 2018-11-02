""" Tests for handler functions. """
from time import time

import jwt
import mock
from django.conf import settings
from django.test import TestCase, override_settings
from oscar.test.factories import UserFactory
from waffle.testutils import override_switch

from ecommerce.extensions.api.handlers import jwt_decode_handler

ISSUERS = ('test-issuer', 'another-issuer',)
SIGNING_KEYS = ('insecure-secret-key', 'secret', 'another-secret',)


def generate_jwt_token(payload, signing_key=None):
    """Generate a valid JWT token for authenticated requests."""
    signing_key = signing_key or settings.JWT_AUTH['JWT_SECRET_KEY']
    return jwt.encode(payload, signing_key).decode('utf-8')


def generate_jwt_payload(user, issuer=None):
    """Generate a valid JWT payload given a user."""
    now = int(time())
    ttl = 5
    issuer = issuer or settings.JWT_AUTH['JWT_ISSUERS'][0]
    return {
        'iss': issuer,
        'username': user.username,
        'email': user.email,
        'iat': now,
        'exp': now + ttl
    }


class JWTDecodeHandlerTests(TestCase):
    """ Tests for the `jwt_decode_handler` utility function. """

    def setUp(self):
        super(JWTDecodeHandlerTests, self).setUp()
        self.user = UserFactory()
        self.payload = generate_jwt_payload(self.user)
        self.jwt = generate_jwt_token(self.payload)

    @mock.patch('edx_django_utils.monitoring.set_custom_metric')
    @mock.patch('ecommerce.extensions.api.handlers.logger')
    def test_decode_success(self, mock_logger, mock_set_custom_metric):
        self.assertEqual(jwt_decode_handler(self.jwt), self.payload)
        mock_set_custom_metric.assert_called_with('ecom_jwt_decode_handler', 'ecommerce-original')
        mock_logger.exception.assert_not_called()

    def test_decode_success_with_multiple_issuers(self):
        settings.JWT_AUTH['JWT_ISSUERS'] = ISSUERS

        for issuer in ISSUERS:
            self.payload['iss'] = issuer
            token = generate_jwt_token(self.payload)
            self.assertEqual(jwt_decode_handler(token), self.payload)

    def test_decode_success_with_multiple_signing_keys(self):
        settings.JWT_AUTH['JWT_SECRET_KEYS'] = SIGNING_KEYS

        for signing_key in SIGNING_KEYS:
            token = generate_jwt_token(self.payload, signing_key)
            self.assertEqual(jwt_decode_handler(token), self.payload)

    @override_switch('jwt_decode_handler.log_exception.ecommerce-original', active=True)
    def test_decode_error(self):
        # Update the payload to ensure a validation error
        self.payload['exp'] = 0
        token = generate_jwt_token(self.payload)

        with mock.patch('ecommerce.extensions.api.handlers.logger') as mock_logger:
            with self.assertRaises(jwt.InvalidTokenError):
                jwt_decode_handler(token)

            mock_logger.exception.assert_called_with('Original JWT decode failed!')
            mock_logger.info.assert_called_with('Failed to use original jwt_decode_handler.', exc_info=True)

    @override_settings(
        JWT_AUTH={
            'JWT_ISSUERS': [{
                'AUDIENCE': 'test-audience',
                'ISSUER': 'test-issuer',
                'SECRET_KEY': 'test-secret-key',
            }],
            'JWT_VERIFY_AUDIENCE': False,
        }
    )
    @mock.patch('edx_django_utils.monitoring.set_custom_metric')
    def test_decode_success_edx_drf_extensions(self, mock_set_custom_metric):
        """
        Should pass using the edx-drf-extensions jwt_decode_handler.

        This would happen with the combination of the JWT_ISSUERS configured in
        the way that edx-drf-extensions is expected, and using the secret-key
        of the first configured issuer.
        """
        payload = generate_jwt_payload(self.user, issuer='test-issuer')
        token = generate_jwt_token(payload, 'test-secret-key')
        self.assertDictContainsSubset(payload, jwt_decode_handler(token))
        mock_set_custom_metric.assert_called_with('ecom_jwt_decode_handler', 'edx-drf-extensions')

    @override_settings(
        JWT_AUTH={
            'JWT_ISSUERS': [
                {
                    'AUDIENCE': 'test-audience',
                    'ISSUER': 'test-issuer',
                    'SECRET_KEY': 'test-secret-key',
                },
                {
                    'AUDIENCE': 'test-audience',
                    'ISSUER': 'test-invalid-issuer',
                    'SECRET_KEY': 'test-secret-key-2',
                },
                {
                    'AUDIENCE': 'test-audience',
                    'ISSUER': 'test-issuer-2',
                    'SECRET_KEY': 'test-secret-key-2',
                },
            ],
            'JWT_VERIFY_AUDIENCE': False,
        }
    )
    @mock.patch('edx_django_utils.monitoring.set_custom_metric')
    @mock.patch('ecommerce.extensions.api.handlers.logger')
    def test_decode_success_updated_config(self, mock_logger, mock_set_custom_metric):
        """
        Should pass using ``_ecommerce_jwt_decode_handler_updated_configs``.

        This would happen with the combination of the JWT_ISSUERS configured in
        the way that edx-drf-extensions is expected, but when the token was
        generated from the second issuer.
        """
        payload = generate_jwt_payload(self.user, issuer='test-issuer-2')
        token = generate_jwt_token(payload, 'test-secret-key-2')
        self.assertDictContainsSubset(payload, jwt_decode_handler(token))
        mock_set_custom_metric.assert_called_with('ecom_jwt_decode_handler', 'ecommerce-updated-config')
        mock_logger.exception.assert_not_called()

    @override_settings(
        JWT_AUTH={
            'JWT_ISSUERS': [
                {
                    'AUDIENCE': 'test-audience',
                    'ISSUER': 'test-issuer',
                    'SECRET_KEY': 'test-secret-key',
                },
                {
                    'AUDIENCE': 'test-audience',
                    'ISSUER': 'test-issuer-2',
                    'SECRET_KEY': 'test-secret-key-2',
                },
            ],
            'JWT_VERIFY_AUDIENCE': False,
            'JWT_SECRET_KEYS': SIGNING_KEYS
        }
    )
    @mock.patch('ecommerce.extensions.api.handlers.logger')
    @override_switch('jwt_decode_handler.log_exception.ecommerce-updated-config', active=True)
    def test_decode_error_invalid_token(self, mock_logger):
        """
        Should fail ``_ecommerce_jwt_decode_handler_updated_configs`` due to
        invalid token, not because it is not configured properly.

        IMPORTANT: The original decode_handler still requires JWT_SECRET_KEYS.
        JWT_SECRET_KEYS cannot be removed from config until the original decode_handler
        code is first removed from the codebase.
        """
        # Update the payload to ensure a validation error
        payload = generate_jwt_payload(self.user, issuer='test-issuer-2')
        payload['exp'] = 0
        token = generate_jwt_token(payload, 'test-secret-key-2')
        with self.assertRaises(jwt.InvalidTokenError):
            jwt_decode_handler(token)

            mock_logger.exception.assert_called_with('Custom config JWT decode failed!')
            mock_logger.info.assert_called_with(
                'Failed to use custom jwt_decode_handler with updated configs.',
                exc_info=True,
            )

    @mock.patch('ecommerce.extensions.api.handlers.logger')
    @override_switch('jwt_decode_handler.log_exception.edx-drf-extensions', active=True)
    def test_decode_with_edx_drf_extensions_log(self, mock_logger):
        self.assertEqual(jwt_decode_handler(self.jwt), self.payload)
        mock_logger.info.assert_called_with('Failed to use edx-drf-extensions jwt_decode_handler.', exc_info=True)
