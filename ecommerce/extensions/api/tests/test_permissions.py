

from rest_framework.parsers import JSONParser
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory, force_authenticate

from ecommerce.extensions.api.permissions import CanActForUser
from ecommerce.tests.testcases import TestCase


class PermissionsTestMixin:
    def get_request(self, user=None, data=None):
        request = APIRequestFactory().post('/', data)

        if user:
            force_authenticate(request, user=user)

        return Request(request, parsers=(JSONParser(),))


class CanActForUserTests(PermissionsTestMixin, TestCase):
    permissions_class = CanActForUser()

    def test_has_permission_no_data(self):
        """ If no username is supplied with the request data, return False. """
        request = self.get_request()
        self.assertFalse(self.permissions_class.has_permission(request, None))

    def test_has_permission_staff(self):
        """ Return True if request.user is a staff user. """
        user = self.create_user(is_staff=True)

        # Data is required, even if you're a staff user.
        request = self.get_request(user=user)
        self.assertFalse(self.permissions_class.has_permission(request, None))

        # Staff can create their own refunds
        request = self.get_request(user=user, data={'username': user.username})
        self.assertTrue(self.permissions_class.has_permission(request, None))

        # Staff can create refunds for other users
        request = self.get_request(user=user, data={'username': 'other_guy'})
        self.assertTrue(self.permissions_class.has_permission(request, None))

    def test_has_permission_same_user(self):
        """ If the request.data['username'] matches request.user, return True. """
        user = self.create_user()

        # Normal users can create their own refunds
        request = self.get_request(user=user, data={'username': user.username})
        self.assertTrue(self.permissions_class.has_permission(request, None))

        # Normal users CANNOT create refunds for other users
        request = self.get_request(user=user, data={'username': 'other_guy'})
        self.assertFalse(self.permissions_class.has_permission(request, None))
