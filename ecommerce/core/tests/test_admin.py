

from django.contrib import messages
from django.urls import reverse

from ecommerce.core.constants import USER_LIST_VIEW_SWITCH
from ecommerce.core.tests import toggle_switch
from ecommerce.tests.factories import UserFactory
from ecommerce.tests.testcases import TestCase


class UserAdminTests(TestCase):

    user_page_url = reverse('admin:core_user_changelist')

    def setUp(self):
        super(UserAdminTests, self).setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True, password=self.password)
        self.client.login(username=self.user.username, password=self.password)

    def test_changelist_view_enable_switch(self):
        """ Default template will load on the list page, if the switch is enabled. """
        toggle_switch(USER_LIST_VIEW_SWITCH, True)
        response = self.client.get(self.user_page_url)
        self.assertEqual(response.status_code, 200)

    def test_changelist_view_disable_switch(self):
        """ Overridden template will load on the list page, if the switch is disabled. """
        toggle_switch(USER_LIST_VIEW_SWITCH, False)
        response = self.client.get(self.user_page_url)
        self.assertEqual(response.status_code, 200)
        msg = 'User administration has been disabled due to the load on the database. ' \
              'This functionality can be restored by activating the {switch_name} Waffle switch. ' \
              'Be careful when re-activating this switch!'.format(switch_name=USER_LIST_VIEW_SWITCH)
        self.assertEqual(response.status_code, 200)
        message = list(response.context['messages'])[0]
        self.assertEqual(message.level, messages.WARNING)
        self.assertEqual(message.message, msg)

    def test_user_factory_lms_user_id(self):
        """
        Test that the UserFactory creates users with an LMS user id.
        """
        self.assertIsNotNone(self.user.lms_user_id)
        self.assertEqual(UserFactory.lms_user_id, self.user.lms_user_id)
