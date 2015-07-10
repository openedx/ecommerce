from django.test import RequestFactory
from oscar.test import factories
from oscar.test.newfactories import ProductAttributeValueFactory

from ecommerce.extensions.api.serializers import OrderSerializer
from ecommerce.tests.mixins import UserMixin, ThrottlingMixin

JSON_CONTENT_TYPE = 'application/json'


class OrderDetailViewTestMixin(ThrottlingMixin, UserMixin):
    def url(self):
        raise NotImplementedError

    def setUp(self):
        super(OrderDetailViewTestMixin, self).setUp()

        user = self.create_user()
        self.order = factories.create_order(user=user)

        # Add a product attribute to one of the order items
        ProductAttributeValueFactory(product=self.order.lines.first().product)

        self.token = self.generate_jwt_token_header(user)

    def test_get_order(self):
        """Test successful order retrieval."""
        request = RequestFactory().get(self.url)
        response = self.client.get(self.url, HTTP_AUTHORIZATION=self.token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, OrderSerializer(self.order, context={'request': request}).data)

    def test_order_wrong_user(self):
        """Test scenarios where an order should return a 404 due to the wrong user."""
        other_user = self.create_user()
        other_token = self.generate_jwt_token_header(other_user)
        response = self.client.get(self.url, HTTP_AUTHORIZATION=other_token)
        self.assertEqual(response.status_code, 404)


class TestServerUrlMixin(object):
    def get_full_url(self, path):
        """ Returns a complete URL with the given path. """
        return 'http://testserver' + path
