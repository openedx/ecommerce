import json

import ddt
import mock
from django.core.urlresolvers import reverse
from requests.exceptions import HTTPError, Timeout
from rest_framework import status

from ecommerce.core.models import User
from ecommerce.extensions.api.v2.tests.views import JSON_CONTENT_TYPE
from ecommerce.extensions.payment.utils import SDNClient
from ecommerce.tests.testcases import TestCase


@ddt.ddt
class SDNCheckViewSetTests(TestCase):
    PATH = reverse('api:v2:sdn:search')

    def setUp(self):
        super(SDNCheckViewSetTests, self).setUp()
        user = self.create_user()
        self.client.login(username=user.username, password=self.password)
        self.site.siteconfiguration.enable_sdn_check = True
        self.site.siteconfiguration.save()

    def make_request(self):
        """Make a POST request to the endpoint."""
        return self.client.post(
            self.PATH,
            data=json.dumps({
                'name': 'Tester',
                'city': 'Testlandia',
                'country': 'TE'
            }),
            content_type=JSON_CONTENT_TYPE
        )

    def test_authentication_required(self):
        """Verify only authenticated users can access endpoint."""
        self.client.logout()
        self.assertEqual(self.make_request().status_code, status.HTTP_401_UNAUTHORIZED)

    @ddt.data(0, 1)
    def test_sdn_check_match(self, hits):
        """Verify the endpoint returns the number of hits SDN check made."""
        with mock.patch.object(SDNClient, 'search', return_value={'total': hits}) as sdn_validator_mock:
            with mock.patch.object(User, 'deactivate_account', return_value=True):
                response = self.make_request()
                self.assertTrue(sdn_validator_mock.called)
                self.assertEqual(json.loads(response.content)['hits'], hits)

    def test_user_logged_out(self):
        """User is logged out after an SDN match."""
        with mock.patch.object(SDNClient, 'search', return_value={'total': 1}) as sdn_validator_mock:
            with mock.patch.object(User, 'deactivate_account', return_value=True):
                self.make_request()
                self.assertTrue(sdn_validator_mock.called)
                self.assertEqual(self.make_request().status_code, status.HTTP_401_UNAUTHORIZED)

    @ddt.data(HTTPError, Timeout)
    def test_sdn_check_error(self, side_effect):
        """Zero hits are returned when an exception happens."""
        with mock.patch.object(SDNClient, 'search') as sdn_validator_mock:
            sdn_validator_mock.side_effect = side_effect
            response = self.make_request()
            self.assertEqual(json.loads(response.content)['hits'], 0)
