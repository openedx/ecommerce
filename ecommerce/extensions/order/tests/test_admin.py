

from django.contrib import messages
from django.urls import reverse

from ecommerce.core.tests import toggle_switch
from ecommerce.extensions.order.constants import ORDER_LIST_VIEW_SWITCH
from ecommerce.tests.factories import UserFactory
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

    def test_changelist_view_disable_switch(self):
        """ Overridden template will load on the list page, if the switch is disabled. """
        toggle_switch(ORDER_LIST_VIEW_SWITCH, False)
        response = self.client.get(self.order_page_url)
        msg = 'Order administration has been disabled due to the load on the database. ' \
              'This functionality can be restored by activating the {switch_name} Waffle switch. ' \
              'Be careful when re-activating this switch!'.format(switch_name=ORDER_LIST_VIEW_SWITCH)
        self.assertEqual(response.status_code, 200)
        message = list(response.context['messages'])[0]
        self.assertEqual(message.level, messages.WARNING)
        self.assertEqual(message.message, msg)
