from django.test import TestCase
from django_dynamic_fixture import G
from social.apps.django_app.default.models import UserSocialAuth

from ecommerce.user.models import User


class UserTests(TestCase):
    def test_access_token(self):
        user = G(User)
        self.assertIsNone(user.access_token)

        social_auth = G(UserSocialAuth, user=user)
        self.assertIsNone(user.access_token)

        access_token = u'My voice is my passport. Verify me.'
        social_auth.extra_data[u'access_token'] = access_token
        social_auth.save()
        self.assertEqual(user.access_token, access_token)
