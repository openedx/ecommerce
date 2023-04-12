"""
Tests for subscriptions API permissions
"""

from ecommerce.bff.subscriptions.permissions import CanGetProductEntitlementInfo
from ecommerce.tests.testcases import TestCase


class CanGetProductEntitlementInfoTest(TestCase):
    """ Tests for get product entitlement API permissions """

    def test_api_permission_staff(self):
        self.user = self.create_user(is_staff=True)
        self.request.user = self.user
        result = CanGetProductEntitlementInfo().has_permission(self.request, None)
        assert result is True

    def test_api_permission_user_granted_permission(self):
        user = self.create_user()
        self.request.user = user

        with self.settings(SUBSCRIPTIONS_SERVICE_WORKER_USERNAME=user.username):
            result = CanGetProductEntitlementInfo().has_permission(self.request, None)
            assert result is True

    def test_api_permission_superuser(self):
        self.user = self.create_user(is_superuser=True)
        self.request.user = self.user
        result = CanGetProductEntitlementInfo().has_permission(self.request, None)
        assert result is True

    def test_api_permission_user_not_granted_permission(self):
        self.user = self.create_user()
        self.request.user = self.user
        result = CanGetProductEntitlementInfo().has_permission(self.request, None)
        assert result is False
