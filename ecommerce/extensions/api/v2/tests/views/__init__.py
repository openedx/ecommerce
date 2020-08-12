

from django.test import RequestFactory
from django.urls import reverse
from oscar.core.loading import get_class, get_model
from oscar.test.factories import ProductAttributeValueFactory

from ecommerce.core.constants import ISO_8601_FORMAT
from ecommerce.extensions.api.serializers import OrderSerializer
from ecommerce.extensions.test import factories
from ecommerce.tests.mixins import ThrottlingMixin

JSON_CONTENT_TYPE = 'application/json'
Product = get_model('catalogue', 'Product')
Selector = get_class('partner.strategy', 'Selector')


class OrderDetailViewTestMixin(ThrottlingMixin):
    @property
    def url(self):
        raise NotImplementedError

    def setUp(self):
        super(OrderDetailViewTestMixin, self).setUp()

        user = self.create_user()
        self.order = factories.create_order(site=self.site, user=user)

        # Add a product attribute to one of the order items
        ProductAttributeValueFactory(product=self.order.lines.first().product)

        self.token = self.generate_jwt_token_header(user)

    def serialize_order(self, order):
        request = RequestFactory(SERVER_NAME=self.site.domain).get('/')
        return OrderSerializer(order, context={'request': request}).data

    def test_get_order(self):
        """Test successful order retrieval."""
        response = self.client.get(self.url, HTTP_AUTHORIZATION=self.token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.serialize_order(self.order))

    def test_order_wrong_user(self):
        """Test scenarios where an order should return a 404 due to the wrong user."""
        other_user = self.create_user()
        other_token = self.generate_jwt_token_header(other_user)
        response = self.client.get(self.url, HTTP_AUTHORIZATION=other_token)
        self.assertEqual(response.status_code, 404)


class ProductSerializerMixin:
    def serialize_product(self, product):
        """ Serializes a Product to a Python dict. """
        attribute_values = [
            {
                'name': av.attribute.name,
                'code': av.attribute.code,
                'value': av.value
            } for av in product.attribute_values.all()
        ]
        data = {
            'id': product.id,
            'url': self.get_full_url(reverse('api:v2:product-detail', kwargs={'pk': product.id})),
            'structure': product.structure,
            'product_class': str(product.get_product_class()),
            'title': product.title,
            'expires': product.expires.strftime(ISO_8601_FORMAT) if product.expires else None,
            'attribute_values': attribute_values,
            'stockrecords': [self.serialize_stockrecord(record) for record in product.stockrecords.all()]
        }

        info = Selector().strategy().fetch_for_product(product)
        data.update({
            'is_available_to_buy': info.availability.is_available_to_buy,
            'price': "{0:.2f}".format(info.price.excl_tax) if info.availability.is_available_to_buy else None
        })

        return data

    def serialize_stockrecord(self, stockrecord):
        """ Serialize a stock record to a python dict. """
        return {
            'id': stockrecord.id,
            'partner': stockrecord.partner.id,
            'product': stockrecord.product.id,
            'partner_sku': stockrecord.partner_sku,
            'price_currency': stockrecord.price_currency,
            'price_excl_tax': str(stockrecord.price_excl_tax),
        }
