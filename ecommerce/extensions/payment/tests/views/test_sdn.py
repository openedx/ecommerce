
import json

import mock
from django.urls import reverse
from requests.exceptions import HTTPError

from ecommerce.extensions.api.tests.test_authentication import AccessTokenMixin
from ecommerce.extensions.payment.models import SDNCheckFailure
from ecommerce.tests.testcases import TestCase


class SDNFailureTests(TestCase):
    failure_path = reverse('sdn:failure')

    def test_sdn_logout_context(self):
        """SDN logout view needs to have the logout URL in its context."""
        logout_url = self.site.siteconfiguration.build_lms_url('logout')
        response = self.client.get(self.failure_path)
        self.assertEqual(response.context['logout_url'], logout_url)


class SDNCheckViewTests(AccessTokenMixin, TestCase):
    sdn_check_path = reverse('sdn:check')

    def setUp(self):
        super().setUp()
        self.user = self.create_user(is_staff=True)
        self.client.login(username=self.user.username, password=self.password)
        self.token = self.generate_jwt_token_header(self.user)
        self.post_params = {
            'lms_user_id': 1337,
            'name': 'Bowser, King of the Koopas',
            'city': 'Northern Chocolate Island',
            'country': 'Mushroom Kingdom',
        }

    def test_sdn_check_missing_args(self):
        response = self.client.post(self.sdn_check_path, HTTP_AUTHORIZATION=self.token)
        assert response.status_code == 400

    @mock.patch('ecommerce.extensions.payment.views.sdn.checkSDNFallback')
    @mock.patch('ecommerce.extensions.payment.views.sdn.SDNClient.search')
    def test_sdn_check_search_fails_uses_fallback(self, mock_search, mock_fallback):
        mock_search.side_effect = [HTTPError]
        mock_fallback.return_value = 0
        response = self.client.post(self.sdn_check_path, data=self.post_params, HTTP_AUTHORIZATION=self.token)
        assert response.status_code == 200
        assert response.json()['hit_count'] == 0

    @mock.patch('ecommerce.extensions.payment.views.sdn.checkSDNFallback')
    @mock.patch('ecommerce.extensions.payment.views.sdn.SDNClient.search')
    def test_sdn_check_search_succeeds(self, mock_search, mock_fallback):
        mock_search.return_value = {'total': 4}
        response = self.client.post(self.sdn_check_path, data=self.post_params, HTTP_AUTHORIZATION=self.token)
        assert response.status_code == 200
        assert response.json()['hit_count'] == 4
        assert response.json()['sdn_response'] == {'total': 4}
        mock_fallback.assert_not_called()


class SDNCheckFailureViewTests(TestCase):
    sdn_check_path = reverse('sdn:metadata')

    def setUp(self):
        super().setUp()
        self.user = self.create_user(is_staff=True)
        self.client.login(username=self.user.username, password=self.password)
        self.token = self.generate_jwt_token_header(self.user)
        self.post_params = {
            'full_name': 'Princess Peach',
            'username': 'toadstool_is_cool',
            'city': 'Mushroom Castle',
            'country': 'US',
            'sdn_check_response': {  # This will be a large JSON blob when returned from SDN API
                'total': 1,
            },
        }

    def test_non_staff_cannot_access_endpoint(self):
        self.user.is_staff = False
        self.user.save()
        response = self.client.post(self.sdn_check_path, data=self.post_params, content_type='application/json',
                                    HTTP_AUTHORIZATION=self.token)
        assert response.status_code == 403

    def test_missing_payload_arg_400(self):
        del self.post_params['full_name']
        response = self.client.post(self.sdn_check_path, data=self.post_params, content_type='application/json',
                                    HTTP_AUTHORIZATION=self.token)
        assert response.status_code == 400

    def test_sdn_response_response_missing_required_field_400(self):
        del self.post_params['sdn_check_response']['total']
        assert 'sdn_check_response' in self.post_params  # so it's clear we deleted the sub dict's key

        response = self.client.post(self.sdn_check_path, data=self.post_params, content_type='application/json',
                                    HTTP_AUTHORIZATION=self.token)
        assert response.status_code == 400

    def test_happy_path_create(self):
        assert SDNCheckFailure.objects.count() == 0
        json_payload = json.dumps(self.post_params)
        response = self.client.post(self.sdn_check_path, data=json_payload, content_type='application/json',
                                    HTTP_AUTHORIZATION=self.token)

        assert response.status_code == 201
        assert SDNCheckFailure.objects.count() == 1

        check_failure_object = SDNCheckFailure.objects.first()
        assert check_failure_object.full_name == 'Princess Peach'
        assert check_failure_object.username == 'toadstool_is_cool'
        assert check_failure_object.city == 'Mushroom Castle'
        assert check_failure_object.country == 'US'
        assert check_failure_object.sdn_check_response == {'total': 1}
