from mock import MagicMock, patch

from requests.exceptions import Timeout

from rest_framework.parsers import JSONParser
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory, force_authenticate

from ecommerce.extensions.api.permissions import CanActForUser, HasDataAPIDjangoGroupAccess
from ecommerce.tests.testcases import TestCase


class PermissionsTestMixin(object):
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


class TestHasDataAPIDjangoGroupAccess(TestCase):
    """
    Tests of the HasDataAPIDjangoGroupAccess permission
    """

    def setUp(self):
        super(TestHasDataAPIDjangoGroupAccess, self).setUp()
        self.enterprise_id = 'fake-enterprise-id'
        self.user = self.create_user()
        self.request = APIRequestFactory().post('/')
        self.request.user = self.user
        self.request.site = MagicMock()
        self.request.auth = MagicMock()
        self.request.parser_context = {
            'kwargs': {
                'enterprise_id': self.enterprise_id
            }
        }
        enterprise_api_client = patch('ecommerce.extensions.api.permissions.get_with_access_to')
        self.enterprise_api_client = enterprise_api_client.start()
        self.addCleanup(enterprise_api_client.stop)
        self.permission = HasDataAPIDjangoGroupAccess()

    def test_staff_access_without_group_permission(self):
        self.user.is_staff = True
        self.enterprise_api_client.return_value = {}
        self.assertFalse(self.permission.has_permission(self.request, None))

    def test_staff_access_with_group_permission(self):
        self.user.is_staff = True
        self.enterprise_api_client.return_value = {
            'uuid': self.enterprise_id
        }
        self.assertTrue(self.permission.has_permission(self.request, None))

    def test_enterprise_user_has_access_with_group_permission(self):
        self.enterprise_api_client.return_value = {
            'uuid': self.enterprise_id
        }
        self.assertTrue(self.permission.has_permission(self.request, None))

    def test_enterprise_user_without_group_permission(self):
        self.enterprise_api_client.return_value = {}
        self.assertFalse(self.permission.has_permission(self.request, None))

    def test_access_without_enterprise_id_in_url(self):
        self.user.is_staff = True
        self.enterprise_api_client.return_value = {
            'uuid': self.enterprise_id
        }
        self.request.parser_context = {}
        enterprise_customer = {
            'results': [
                {
                    "enterprise_customer": {
                        "uuid": "cf246b88-d5f6-4908-a522-fc307e0b0c59",
                        "name": "BigEnterprise",
                    }
                }],
            'count': 1
        }
        with patch('ecommerce.extensions.api.permissions.fetch_enterprise_learner_data',
                   return_value=enterprise_customer):
            self.assertTrue(self.permission.has_permission(self.request, None))

    def test_access_without_enterprise_id_in_url_exception(self):
        self.user.is_staff = True
        self.enterprise_api_client.return_value = {
            'uuid': self.enterprise_id
        }
        self.request.parser_context = {}
        enterprise_customer = {
            'results': [
                {
                    "enterprise_customer": {
                        "uuid": "cf246b88-d5f6-4908-a522-fc307e0b0c59",
                        "name": "BigEnterprise",
                    }
                }],
            'count': 1
        }
        with patch('ecommerce.extensions.api.permissions.fetch_enterprise_learner_data',
                   return_value=enterprise_customer, side_effect=Timeout):
            self.assertFalse(self.permission.has_permission(self.request, None))

    def test_access_without_enterprise_id_and_enterprise_customer(self):
        self.user.is_staff = True
        self.enterprise_api_client.return_value = None
        self.request.parser_context = {}
        enterprise_customer = {
            'results': [{}],
            'count': 0
        }
        with patch('ecommerce.extensions.api.permissions.fetch_enterprise_learner_data',
                   return_value=enterprise_customer):
            self.assertFalse(self.permission.has_permission(self.request, None))
