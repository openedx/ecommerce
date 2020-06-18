

from django.contrib import messages
from django.contrib.auth.models import AnonymousUser
from django.urls import reverse

from ecommerce.core.constants import ORDER_MANAGER_ROLE
from ecommerce.core.models import EcommerceFeatureRole, EcommerceFeatureRoleAssignment
from ecommerce.core.tests import toggle_switch
from ecommerce.extensions.refund.constants import REFUND_LIST_VIEW_SWITCH
from ecommerce.extensions.refund.tests.factories import RefundFactory
from ecommerce.tests.factories import UserFactory
from ecommerce.tests.testcases import TestCase


class RefundAdminTests(TestCase):

    refund_page_url = reverse('admin:refund_refund_changelist')

    def setUp(self):
        super(RefundAdminTests, self).setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True, password=self.password)
        self.client.login(username=self.user.username, password=self.password)
        self.role = EcommerceFeatureRole.objects.get(name=ORDER_MANAGER_ROLE)

    def has_perm(self, user):
        """ Checks admin permission for Refund module """
        order_manager_permissions = [
            'refund.add_refund',
            'refund.change_refund',
            'refund.delete_refund',
            'refund.add_refundline',
            'refund.change_refundline',
            'refund.delete_refundline',
        ]

        return all(map(user.has_perm, order_manager_permissions))

    def test_changelist_view_enable_switch(self):
        """ Default template will load on the list page, if the switch is enabled. """
        toggle_switch(REFUND_LIST_VIEW_SWITCH, True)
        response = self.client.get(self.refund_page_url)
        self.assertEqual(response.status_code, 200)

    def test_changelist_view_disable_switch(self):
        """ Overridden template will load on the list page, if the switch is disabled. """
        toggle_switch(REFUND_LIST_VIEW_SWITCH, False)
        response = self.client.get(self.refund_page_url)
        msg = 'Refund administration has been disabled due to the load on the database. ' \
              'This functionality can be restored by activating the {switch_name} Waffle switch. ' \
              'Be careful when re-activating this switch!'.format(switch_name=REFUND_LIST_VIEW_SWITCH)
        self.assertEqual(response.status_code, 200)
        message = list(response.context['messages'])[0]
        self.assertEqual(message.level, messages.WARNING)
        self.assertEqual(message.message, msg)

    def test_edit_view_with_disable_switch(self):
        """ Test that edit refund page still works even if the switch is disabled. """
        toggle_switch(REFUND_LIST_VIEW_SWITCH, False)
        refund = RefundFactory()
        edit_page_url = reverse('admin:refund_refund_change', args=(refund.id,))
        response = self.client.get(edit_page_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, refund.order.number)

    def test_explicit_access(self):
        """
        Staff user can add, delete and change Refund and RefundLine model from django admin if
        they are assigned `ORDER_MANAGER_ROLE`
        """
        self.user.is_superuser = False
        EcommerceFeatureRoleAssignment.objects.get_or_create(role=self.role, user=self.user)
        self.assertTrue(self.has_perm(self.user))

    def test_no_explicit_access(self):
        """
        Staff user cannot add, delete and change Refund model from django admin if
        they are not assigned `ORDER_MANAGER_ROLE`
        """
        self.user.is_superuser = False
        self.assertFalse(self.has_perm(self.user))

    def test_anonymous_user(self):
        """
        Test that if an Anonymous or unauthenticated user tries to access refund admin module
        permission is denied
        """
        user = AnonymousUser()
        self.assertFalse(self.has_perm(user))
