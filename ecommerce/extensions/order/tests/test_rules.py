
from django.urls import reverse

from ecommerce.core.constants import ORDER_MANAGER_ROLE, STUDENT_SUPPORT_ADMIN_ROLE
from ecommerce.core.models import EcommerceFeatureRole, EcommerceFeatureRoleAssignment
from ecommerce.extensions.order import rules
from ecommerce.tests.factories import UserFactory
from ecommerce.tests.mixins import JwtMixin
from ecommerce.tests.testcases import TestCase


class OrderRulesTests(TestCase, JwtMixin):

    def setUp(self):
        super(OrderRulesTests, self).setUp()
        self.user = UserFactory(is_staff=True, is_superuser=False, password=self.password)
        self.client.login(username=self.user.username, password=self.password)
        self.role = EcommerceFeatureRole.objects.get(name=ORDER_MANAGER_ROLE)

    def test_explicit_access(self):
        """
        Verify that staff user has explicit access if they are assigned `ORDER_MANAGER_ROLE`.
        """
        EcommerceFeatureRoleAssignment.objects.get_or_create(role=self.role, user=self.user)
        self.assertTrue(rules.request_user_has_explicit_access(self.user))

    def test_no_explicit_access(self):
        """
        Verify that staff user does not have explicit access if they are not assigned `ORDER_MANAGER_ROLE`.
        """
        self.assertFalse(rules.request_user_has_explicit_access(self.user))

    def test_implicit_access(self):
        """
        Verify that staff user have implicit access if they are assigned system wide
        `STUDENT_SUPPORT_ADMIN_ROLE`.
        """
        EcommerceFeatureRoleAssignment.objects.all().delete()
        self.set_jwt_cookie(system_wide_role=STUDENT_SUPPORT_ADMIN_ROLE, context=None)
        response = self.client.get(reverse('admin:order_markordersstatuscompleteconfig_changelist'))
        self.assertEqual(response.status_code, 200)

    def test_no_implicit_access(self):
        """
        Verify that staff user does not have implicit access if they are not assigned
        system wide `STUDENT_SUPPORT_ADMIN_ROLE`.
        """
        EcommerceFeatureRoleAssignment.objects.all().delete()
        response = self.client.get(reverse('admin:order_markordersstatuscompleteconfig_changelist'))
        self.assertNotEqual(response.status_code, 200)
