from django.test import TestCase
from ecommerce.extensions.test.factories import UserFactory
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory, force_authenticate

from ecommerce.extensions.api.permissions import CanActForUser


class CanActForUserTests(TestCase):
    permissions_class = CanActForUser()

    def _get_request(self, data=None, user=None):
        request = APIRequestFactory().post('/', data)

        if user:
            force_authenticate(request, user=user)

        return Request(request)

    def test_has_permission_no_data(self):
        """ If no username is supplied with the request data, return False. """
        request = self._get_request()
        self.assertFalse(self.permissions_class.has_permission(request, None))

    def test_has_permission_superuser(self):
        """ Return True if request.user is a superuser. """
        user = UserFactory(is_superuser=True)

        # Data is required, even if you're a superuser.
        request = self._get_request(user=user)
        self.assertFalse(self.permissions_class.has_permission(request, None))

        # Superusers can create their own refunds
        request = self._get_request(data={'username': user.username}, user=user)
        self.assertTrue(self.permissions_class.has_permission(request, None))

        # Superusers can create refunds for other users
        request = self._get_request(data={'username': 'other_guy'}, user=user)
        self.assertTrue(self.permissions_class.has_permission(request, None))

    def test_has_permission_same_user(self):
        """ If the request.data['username'] matches request.user, return True. """
        user = UserFactory()

        # Normal users can create their own refunds
        request = self._get_request(data={'username': user.username}, user=user)
        self.assertTrue(self.permissions_class.has_permission(request, None))

        # Normal users CANNOT create refunds for other users
        request = self._get_request(data={'username': 'other_guy'}, user=user)
        self.assertFalse(self.permissions_class.has_permission(request, None))
