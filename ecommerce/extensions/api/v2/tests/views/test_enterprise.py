from __future__ import unicode_literals

import httpretty
import mock
from django.core.urlresolvers import reverse

from ecommerce.enterprise.tests.mixins import EnterpriseServiceMockMixin
from ecommerce.tests.testcases import TestCase


class TestEnterpriseCustomerView(EnterpriseServiceMockMixin, TestCase):

    dummy_enterprise_customer_data = {
        'results': [
            {
                'name': 'Starfleet Academy',
                'uuid': '5113b17bf79f4b5081cf3be0009bc96f',
                'hypothetical_private_info': 'seriously, very private',
            },
            {
                'name': 'Millennium Falcon',
                'uuid': 'd1fb990fa2784a52a44cca1118ed3993',
            }
        ]
    }

    @mock.patch('ecommerce.enterprise.utils.EdxRestApiClient')
    @httpretty.activate
    def test_get_customers(self, mock_client):
        self.mock_access_token_response()
        instance = mock_client.return_value
        setattr(
            instance,
            'enterprise-customer',
            mock.MagicMock(
                get=mock.MagicMock(
                    return_value=self.dummy_enterprise_customer_data
                )
            ),
        )
        url = reverse('api:v2:enterprise:enterprise_customers')
        result = self.client.get(url)
        self.assertEqual(result.status_code, 401)

        user = self.create_user(is_staff=True)

        self.client.login(username=user.username, password=self.password)

        result = self.client.get(url)
        self.assertEqual(result.status_code, 200)
        self.assertJSONEqual(
            result.content.decode('utf-8'),
            {
                'results': [
                    {
                        'name': 'Starfleet Academy',
                        'id': '5113b17bf79f4b5081cf3be0009bc96f'
                    },  # Note that the private information from the API has been stripped
                    {
                        'name': 'Millennium Falcon',
                        'id': 'd1fb990fa2784a52a44cca1118ed3993'
                    }
                ]
            }
        )
