import json

from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework.test import APIRequestFactory

from ecommerce.extensions.api.v2.views.enrollment_codes import EnrollmentCodeOrderCreateView


class EnrollmentCodeOrderCreateViewTest(APITestCase):

    def test_create(self):
        url = '/api/v2/enrollment_codes/'
        data = {'test': 'data'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 1)
        # factory = APIRequestFactory()
        # response = factory.post(
        #     '/api/v2/enrollment_codes/',
        #     json.dumps({'title': 'new idea'}),
        #     content_type='application/json'
        # )
        # self.assertEqual(response.DATA, 1)


# TODO:
# assert new product (new catalog)
# assert new stock record,
# assert basket creation
# assert order creation
