from django.contrib import messages
from django.urls import reverse
from oscar.test.factories import UserFactory

from ecommerce.core.tests import toggle_switch
from ecommerce.extensions.refund.constants import REFUND_LIST_VIEW_SWITCH
from ecommerce.tests.testcases import TestCase


class RefundAdminTests(TestCase):

    refund_page_url = reverse('admin:refund_refund_changelist')

    def setUp(self):
        super(RefundAdminTests, self).setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True, password=self.password)
        self.client.login(username=self.user.username, password=self.password)

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
