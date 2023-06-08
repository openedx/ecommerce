
import mock
from django.urls import reverse
from requests.exceptions import HTTPError

from ecommerce.tests.testcases import TestCase


class SDNFailureTests(TestCase):
    failure_path = reverse('sdn:failure')

    def test_sdn_logout_context(self):
        """SDN logout view needs to have the logout URL in its context."""
        logout_url = self.site.siteconfiguration.build_lms_url('logout')
        response = self.client.get(self.failure_path)
        self.assertEqual(response.context['logout_url'], logout_url)


class SDNCheckViewTests(TestCase):
    sdn_check_path = reverse('sdn:check')

    def setUp(self):
        super().setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)
        self.post_params = {
            'lms_user_id': 1337,
            'name': 'Bowser, King of the Koopas',
            'city': 'Northern Chocolate Island',
            'country': 'Mushroom Kingdom',
        }

    def test_sdn_check_missing_args(self):
        response = self.client.post(self.sdn_check_path)
        assert response.status_code == 400

    @mock.patch('ecommerce.extensions.payment.views.sdn.checkSDNFallback')
    @mock.patch('ecommerce.extensions.payment.views.sdn.SDNClient.search')
    def test_sdn_check_search_fails_uses_fallback(self, mock_search, mock_fallback):
        mock_search.side_effect = [HTTPError]
        mock_fallback.return_value = 0
        response = self.client.post(self.sdn_check_path, data=self.post_params)
        assert response.status_code == 200
        assert response.json()['hit_count'] == 0

    @mock.patch('ecommerce.extensions.payment.views.sdn.checkSDNFallback')
    @mock.patch('ecommerce.extensions.payment.views.sdn.SDNClient.search')
    def test_sdn_check_search_succeeds(self, mock_search, mock_fallback):
        mock_search.return_value = {'total': 4}
        response = self.client.post(self.sdn_check_path, data=self.post_params)
        assert response.status_code == 200
        assert response.json()['hit_count'] == 4
        mock_fallback.assert_not_called()
