"""
Broadly-useful mixins for use in automated tests.
"""
from django.conf import settings
import jwt
from oscar.test import factories


class UserMixin(object):
    """ Provides utility methods for creating and authenticating users in test cases. """
    password = 'test'

    def create_user(self, **kwargs):
        """ Create a user, with overrideable defaults. """
        return factories.UserFactory(password=self.password, **kwargs)

    def generate_jwt_token_header(self, user, secret=None):
        """ Generate a valid JWT token header for authenticated requests. """
        secret = secret or getattr(settings, 'JWT_AUTH')['JWT_SECRET_KEY']
        payload = {
            'username': user.username,
            'email': user.email,
        }
        return "JWT {token}".format(token=jwt.encode(payload, secret))
