from ecommerce.core.models import User
from ecommerce.tests.testcases import TestCase


class UserTests(TestCase):
    TEST_CONTEXT = {'foo': 'bar', 'baz': None}

    def test_access_token(self):
        user = self.create_user()
        self.assertIsNone(user.access_token)

        self.create_access_token(user)
        self.assertEqual(user.access_token, self.access_token)

    def test_tracking_context(self):
        """ Ensures that the tracking_context dictionary is written / read
        correctly by the User model. """
        user = self.create_user()
        self.assertIsNone(user.tracking_context)

        user.tracking_context = self.TEST_CONTEXT
        user.save()

        same_user = User.objects.get(id=user.id)
        self.assertEqual(same_user.tracking_context, self.TEST_CONTEXT)

    def test_get_full_name(self):
        """ Test that the user model concatenates first and last name if the full name is not set. """
        full_name = "George Costanza"
        user = self.create_user(full_name=full_name)
        self.assertEquals(user.get_full_name(), full_name)

        first_name = "Jerry"
        last_name = "Seinfeld"
        user = self.create_user(full_name=None, first_name=first_name, last_name=last_name)
        expected = "{first_name} {last_name}".format(first_name=first_name, last_name=last_name)
        self.assertEquals(user.get_full_name(), expected)

        user = self.create_user(full_name=full_name, first_name=first_name, last_name=last_name)
        self.assertEquals(user.get_full_name(), full_name)
