from django.core.urlresolvers import reverse
from oscar.test.factories import UserFactory

from ecommerce.core.tests import toggle_switch
from ecommerce.extensions.order.constants import ORDER_LIST_VIEW_SWITCH
from ecommerce.tests.testcases import TestCase


class OrderAdminTests(TestCase):

    order_page_url = reverse('admin:order_order_changelist')

    def setUp(self):
        super(OrderAdminTests, self).setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True, password=self.password)
        self.client.login(username=self.user.username, password=self.password)

    def test_changelist_view_enable_switch(self):
        """ Default template will load on the list page, if the switch is enabled. """
        toggle_switch(ORDER_LIST_VIEW_SWITCH, True)
        response = self.client.get(self.order_page_url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'List view is temporarily disabled due to large number of records.')

    def test_changelist_view_disable_switch(self):
        """ Overridden template will load on the list page, if the switch is disabled. """
        toggle_switch(ORDER_LIST_VIEW_SWITCH, False)
        response = self.client.get(self.order_page_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'List view is temporarily disabled due to large number of records.')
