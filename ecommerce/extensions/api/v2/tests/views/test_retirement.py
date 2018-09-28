import ddt
from rest_framework import status

from ecommerce.extensions.analytics.utils import ECOM_TRACKING_ID_FMT
from ecommerce.extensions.api.v2.views.retirement import EcommerceIdView
from ecommerce.tests.testcases import TestCase


@ddt.ddt
class EcommerceIdViewTest(TestCase):
    def test_successful_get(self):
        user = self.create_user()
        response = EcommerceIdView().get(None, username=user.username)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertDictEqual(
            response.data,
            {
                'id': user.pk,
                'ecommerce_tracking_id': ECOM_TRACKING_ID_FMT.format(user.pk)
            }
        )

    @ddt.data('does_not_exist', None)
    def test_unknown_user(self, username):
        response = EcommerceIdView().get(None, username=username)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
