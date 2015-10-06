from django.core.urlresolvers import reverse
from django.test import RequestFactory
from oscar.core.loading import get_class
from oscar.test import factories
from oscar.test.newfactories import ProductAttributeValueFactory

from ecommerce.core.constants import ISO_8601_FORMAT
from ecommerce.extensions.api.serializers import OrderSerializer
from ecommerce.tests.mixins import UserMixin, ThrottlingMixin

JSON_CONTENT_TYPE = 'application/json'
Selector = get_class('partner.strategy', 'Selector')


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


class ProductSerializerMixin(TestServerUrlMixin):
    def serialize_product(self, product):
        """ Serializes a Product to a Python dict. """
        attribute_values = [{'name': av.attribute.name, 'value': av.value} for av in product.attribute_values.all()]
        data = {
            'id': product.id,
            'url': self.get_full_url(reverse('api:v2:product-detail', kwargs={'pk': product.id})),
            'structure': product.structure,
            'product_class': unicode(product.get_product_class()),
            'title': product.title,
            'expires': product.expires.strftime(ISO_8601_FORMAT) if product.expires else None,
            'attribute_values': attribute_values,
            'stockrecords': self.serialize_stock_records(product.stockrecords.all())
        }

        info = Selector().strategy().fetch_for_product(product)
        data.update({
            'is_available_to_buy': info.availability.is_available_to_buy,
            'price': "{0:.2f}".format(info.price.excl_tax) if info.availability.is_available_to_buy else None
        })

        return data

    def serialize_stock_records(self, stock_records):
        return [
            {
                'id': record.id,
                'partner': record.partner.id,
                'partner_sku': record.partner_sku,
                'price_currency': record.price_currency,
                'price_excl_tax': str(record.price_excl_tax),

            } for record in stock_records
        ]
