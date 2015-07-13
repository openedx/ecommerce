from django.test import TestCase
from django_dynamic_fixture import G
from social.apps.django_app.default.models import UserSocialAuth

from ecommerce.core.models import User


class UserTests(TestCase):
    TEST_CONTEXT = {'foo': 'bar', 'baz': None}

    def test_access_token(self):
        user = G(User)
        self.assertIsNone(user.access_token)

        social_auth = G(UserSocialAuth, user=user)
        self.assertIsNone(user.access_token)

        access_token = u'My voice is my passport. Verify me.'
        social_auth.extra_data[u'access_token'] = access_token
        social_auth.save()
        self.assertEqual(user.access_token, access_token)

    def test_tracking_context(self):
        """ Ensures that the tracking_context dictionary is written / read
        correctly by the User model. """
        user = G(User)
        self.assertIsNone(user.tracking_context)

        user.tracking_context = self.TEST_CONTEXT
        user.save()

        same_user = User.objects.get(id=user.id)
        self.assertEqual(same_user.tracking_context, self.TEST_CONTEXT)

    def test_get_full_name(self):
        """ Test that the user model concatenates first and last name if the full name is not set. """
        full_name = "George Costanza"
        user = G(User, full_name=full_name)
        self.assertEquals(user.get_full_name(), full_name)

        first_name = "Jerry"
        last_name = "Seinfeld"
        user = G(User, full_name=None, first_name=first_name, last_name=last_name)
        expected = "{first_name} {last_name}".format(first_name=first_name, last_name=last_name)
        self.assertEquals(user.get_full_name(), expected)

        user = G(User, full_name=full_name, first_name=first_name, last_name=last_name)
        self.assertEquals(user.get_full_name(), full_name)
