import json

from django.test import TestCase
from rest_framework.test import APIRequestFactory

from ecommerce.extensions.api.v2.views.enrollment_codes import EnrollmentCodeOrderCreateView


class EnrollmentCodeOrderCreateViewTest(TestCase):

    def test_create(self):
        factory = APIRequestFactory()
        request = factory.post(
            '/api/v2/enrollment_codes/',
            json.dumps({'title': 'new idea'}),
            content_type='application/json'
        )
        self.assertEqual(request.data, 1)


# TODO:
# assert new product (new catalog)
# assert new stock record,
# assert basket creation
# assert order creation
