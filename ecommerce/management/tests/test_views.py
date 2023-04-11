

import mock
from django.contrib import messages
from django.urls import reverse

from ecommerce.management.utils import FulfillFrozenBaskets
from ecommerce.tests.testcases import TestCase


class ManagementViewTests(TestCase):
    path = reverse('management:index')

    def setUp(self):
        super(ManagementViewTests, self).setUp()
        self.user = self.create_user(is_staff=True, is_superuser=True)
        self.client.login(username=self.user.username, password=self.password)

    def get_response_messages(self, response):
        return list(response.context['messages'])

    def assert_first_message(self, response, expected_level, expected_msg):
        message = self.get_response_messages(response)[0]
        assert message.message == expected_msg
        assert message.level == expected_level

    def test_login_required(self):
        """ Verify the view requires login. """
        self.client.logout()
        response = self.client.get(self.path)
        assert response.status_code == 302

    def test_superuser_required(self):
        """ Verify the view is not accessible to non-superusers. """
        self.client.logout()
        user = self.create_user()
        self.client.login(username=user.username, password=self.password)
        response = self.client.get(self.path)
        assert response.status_code == 302

    def test_invalid_action(self):
        """ Verify the view responds with an error message if an invalid action is posted. """
        response = self.client.post(self.path, {'action': 'invalid-action'})
        assert response.status_code == 200
        self.assert_first_message(response, messages.ERROR, 'invalid-action is not a valid action.')

    def test_refund_basket_transactions(self):
        success_count = 0
        failed_count = 0
        result = (success_count, failed_count)
        with mock.patch('ecommerce.management.views.refund_basket_transactions', return_value=result) as mock_refund:
            response = self.client.post(self.path, {'action': 'refund_basket_transactions', 'basket_ids': '1,2,3'})
            mock_refund.assert_called_once_with(self.site, [1, 2, 3])

        assert response.status_code == 200
        expected = 'Finished refunding basket transactions. [0] transactions were successfully refunded. ' \
                   '[0] attempts failed.'
        self.assert_first_message(response, messages.INFO, expected)

    def test_fulfill(self):
        with mock.patch.object(FulfillFrozenBaskets, 'fulfill_basket') as mock_fulfill:
            response = self.client.post(self.path, {'action': 'fulfill', 'basket_ids': '1,2,3'})
            mock_fulfill.assert_has_calls([
                mock.call(basket_id=1, site=self.site),
                mock.call(basket_id=2, site=self.site),
                mock.call(basket_id=3, site=self.site),
            ], any_order=True)

        assert response.status_code == 200
