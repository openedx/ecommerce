from __future__ import unicode_literals
import datetime
import json

from django.core.urlresolvers import reverse
from django.test import TestCase
from oscar.core.loading import get_model, get_class
import pytz

from ecommerce.core.constants import ISO_8601_FORMAT
from ecommerce.courses.models import Course
from ecommerce.extensions.api.v2.tests.views import JSON_CONTENT_TYPE, TestServerUrlMixin
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.tests.mixins import UserMixin

Product = get_model('catalogue', 'Product')
ProductClass = get_model('catalogue', 'ProductClass')
Selector = get_class('partner.strategy', 'Selector')


class ProductViewSetTests(TestServerUrlMixin, CourseCatalogTestMixin, UserMixin, TestCase):
    maxDiff = None

    def setUp(self):
        super(ProductViewSetTests, self).setUp()
        self.user = self.create_user(is_staff=True)
        self.client.login(username=self.user.username, password=self.password)
        self.course = Course.objects.create(id='edX/DemoX/Demo_Course', name='Test Course')

        # TODO Update the expiration date by 2099-12-31
        expires = datetime.datetime(2100, 1, 1, tzinfo=pytz.UTC)
        self.seat = self.course.create_or_update_seat('honor', False, 0, expires=expires)

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
            'attribute_values': attribute_values
        }

        info = Selector().strategy().fetch_for_product(product)
        data.update({
            'is_available_to_buy': info.availability.is_available_to_buy,
            'price': "{0:.2f}".format(info.price.excl_tax) if info.availability.is_available_to_buy else None
        })

        return data

    def test_list(self):
        """ Verify a list of products is returned. """
        path = reverse('api:v2:product-list')
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        results = [self.serialize_product(p) for p in self.course.products.all()]
        expected = {'count': 2, 'next': None, 'previous': None, 'results': results}
        self.assertDictEqual(json.loads(response.content), expected)

        # If no products exist, the view should return an empty result set.
        Product.objects.all().delete()
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        expected = {'count': 0, 'next': None, 'previous': None, 'results': []}
        self.assertDictEqual(json.loads(response.content), expected)

    def test_retrieve(self):
        """ Verify a single product is returned. """
        path = reverse('api:v2:product-detail', kwargs={'pk': 999})
        response = self.client.get(path)
        self.assertEqual(response.status_code, 404)

        path = reverse('api:v2:product-detail', kwargs={'pk': self.seat.id})
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertDictEqual(json.loads(response.content), self.serialize_product(self.seat))

    def test_destroy(self):
        """ Verify the view does NOT allow products to be destroyed. """
        product_id = self.seat.id
        path = reverse('api:v2:product-detail', kwargs={'pk': product_id})
        response = self.client.delete(path)
        self.assertEqual(response.status_code, 405)
        self.assertTrue(Product.objects.filter(id=product_id).exists())

    def test_update(self):
        """ Verify the view allows individual products to be updated. """
        data = self.serialize_product(self.seat)
        data['title'] = 'Fake Seat Title'

        path = reverse('api:v2:product-detail', kwargs={'pk': self.seat.id})
        response = self.client.put(path, json.dumps(data), JSON_CONTENT_TYPE)
        self.assertEqual(response.status_code, 200, response.content)

        product = Product.objects.get(id=self.seat.id)
        self.assertEqual(product.title, data['title'])
        self.assertDictEqual(json.loads(response.content), self.serialize_product(product))

    def test_list_for_course(self):
        """ Verify the view supports listing products for a single course. """
        # Create another course and seat to confirm filtering.
        other_course = Course.objects.create(id='edX/DemoX/XYZ', name='Test Course 2')
        other_course.create_or_update_seat('honor', False, 0)

        path = reverse('api:v2:course-product-list', kwargs={'parent_lookup_course_id': self.course.id})
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        results = [self.serialize_product(p) for p in self.course.products.all()]
        expected = {'count': 2, 'next': None, 'previous': None, 'results': results}
        self.assertDictEqual(json.loads(response.content), expected)
