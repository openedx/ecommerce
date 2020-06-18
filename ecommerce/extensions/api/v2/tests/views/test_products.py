

import datetime
import json
import uuid

import ddt
import pytz
from django.test import RequestFactory
from django.urls import reverse
from oscar.core.loading import get_model

from ecommerce.core.constants import COUPON_PRODUCT_CLASS_NAME, COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME
from ecommerce.coupons.tests.mixins import CouponMixin
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.api.serializers import ProductSerializer
from ecommerce.extensions.api.v2.tests.views import JSON_CONTENT_TYPE, ProductSerializerMixin
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.tests.factories import PartnerFactory, ProductFactory
from ecommerce.tests.testcases import TestCase

Benefit = get_model('offer', 'Benefit')
Catalog = get_model('catalogue', 'Catalog')
Product = get_model('catalogue', 'Product')
ProductClass = get_model('catalogue', 'ProductClass')
Voucher = get_model('voucher', 'Voucher')

PRODUCT_LIST_PATH = reverse('api:v2:product-list')


class ProductViewSetBase(ProductSerializerMixin, DiscoveryTestMixin, TestCase):
    def setUp(self):
        super(ProductViewSetBase, self).setUp()
        self.user = self.create_user(is_staff=True)
        self.client.login(username=self.user.username, password=self.password)
        self.course = CourseFactory(id='edX/DemoX/Demo_Course', name='Test Course', partner=self.partner)

        # TODO Update the expiration date by 2099-12-31
        expires = datetime.datetime(2100, 1, 1, tzinfo=pytz.UTC)
        self.seat = self.course.create_or_update_seat('honor', False, 0, expires=expires)


class ProductViewSetTests(ProductViewSetBase):
    def test_list(self):
        """The list endpoint should return only products with current site's partner."""
        ProductFactory.create_batch(3, stockrecords__partner=PartnerFactory())

        response = self.client.get(PRODUCT_LIST_PATH)
        self.assertEqual(Product.objects.count(), 5)
        self.assertEqual(response.status_code, 200)
        results = [self.serialize_product(p) for p in self.course.products.all()]
        expected = {'count': 2, 'next': None, 'previous': None, 'results': results}
        self.assertDictEqual(response.json(), expected)

        # If no products exist, the view should return an empty result set.
        Product.objects.all().delete()
        response = self.client.get(PRODUCT_LIST_PATH)
        self.assertEqual(response.status_code, 200)
        expected = {'count': 0, 'next': None, 'previous': None, 'results': []}
        self.assertDictEqual(response.json(), expected)

    def test_retrieve(self):
        """ Verify a single product is returned. """
        path = reverse('api:v2:product-detail', kwargs={'pk': 999})
        response = self.client.get(path)
        self.assertEqual(response.status_code, 404)

        path = reverse('api:v2:product-detail', kwargs={'pk': self.seat.id})
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertDictEqual(response.json(), self.serialize_product(self.seat))

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
        self.assertDictEqual(response.json(), self.serialize_product(product))

    def test_list_for_course(self):
        """ Verify the view supports listing products for a single course. """
        # Create another course and seat to confirm filtering.
        other_course = CourseFactory(id='edX/DemoX/XYZ', name='Test Course 2', partner=self.partner)
        other_course.create_or_update_seat('honor', False, 0)

        path = reverse('api:v2:course-product-list', kwargs={'parent_lookup_course_id': self.course.id})
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        results = [self.serialize_product(p) for p in self.course.products.all()]
        expected = {'count': 2, 'next': None, 'previous': None, 'results': results}
        self.assertDictEqual(response.json(), expected)

    def test_get_partner_products(self):
        """Verify the endpoint returns the list of products associated with a
        partner.
        """
        url = reverse(
            'api:v2:partner-product-list',
            kwargs={'parent_lookup_stockrecords__partner_id': self.partner.id}
        )
        response = self.client.get(url)
        expected_data = self.serialize_product(self.seat)
        self.assertEqual(response.status_code, 200)
        self.assertListEqual(response.json()['results'], [expected_data])

    def test_no_partner_product(self):
        """Verify the endpoint returns an empty list if no products are
        associated with a partner.
        """
        Product.objects.all().delete()
        url = reverse(
            'api:v2:partner-product-list',
            kwargs={'parent_lookup_stockrecords__partner_id': self.partner.id}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        expected = {
            'count': 0,
            'next': None,
            'previous': None,
            'results': []
        }
        self.assertDictEqual(response.json(), expected)


@ddt.ddt
class ProductViewSetCourseEntitlementTests(ProductViewSetBase):
    def setUp(self):
        self.entitlement_data = {
            'product_class': COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME,
            'title': 'Test Course',
            'price': 50,
            'certificate_type': 'verified',
            'uuid': str(uuid.uuid4()),
        }
        super(ProductViewSetCourseEntitlementTests, self).setUp()

    def test_entitlement_post(self):
        """ Verify the view allows individual Course Entitlement products to be made via post"""
        self.assertEqual(Product.objects.count(), 2)
        response = self.client.post('/api/v2/products/', json.dumps(self.entitlement_data), JSON_CONTENT_TYPE)
        self.assertEqual(response.status_code, 201)
        # count goes up by 2 because it also creates the parent entitlement
        self.assertEqual(Product.objects.count(), 4)

    def test_entitlement_post_bad_request(self):
        """
        Verify the view returns a 400 status code with a message when not all fields
        are provided for Course Entitlement products attempting to be made via post
        """
        del self.entitlement_data['price']
        del self.entitlement_data['title']
        response = self.client.post('/api/v2/products/', json.dumps(self.entitlement_data), JSON_CONTENT_TYPE)
        error_message = 'Missing or bad value for: [price]. Missing or bad value for: [title].'
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, error_message)

    def test_non_entitlement_post(self):
        """ Verify the view does not allow anything but Course Entitlement products to be made via post"""
        self.entitlement_data['product_class'] = 'Seat'
        response = self.client.post('/api/v2/products/', json.dumps(self.entitlement_data), JSON_CONTENT_TYPE)
        error_message = 'Product API only supports POST for Course Entitlement products.'
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, error_message)


class ProductViewSetCouponTests(CouponMixin, ProductViewSetBase):
    def test_coupon_product_details(self):
        """Verify the endpoint returns all coupon information."""
        coupon = self.create_coupon(partner=self.partner)
        url = reverse('api:v2:product-detail', kwargs={'pk': coupon.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        request = RequestFactory(SERVER_NAME=self.site.domain).get('/')
        request.user = self.user
        request.site = self.site
        expected = ProductSerializer(coupon, context={'request': request}).data
        self.assertDictEqual(response.data, expected)

    def test_coupon_voucher_serializer(self):
        """Verify that the vouchers of a coupon are properly serialized."""
        coupon = self.create_coupon(partner=self.partner)
        url = reverse('api:v2:product-detail', kwargs={'pk': coupon.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        response_data = response.json()
        voucher = response_data['attribute_values'][0]['value'][0]
        self.assertEqual(voucher['name'], 'Test coupon')
        self.assertEqual(voucher['usage'], Voucher.SINGLE_USE)
        self.assertEqual(voucher['benefit']['type'], Benefit.PERCENTAGE)
        self.assertEqual(voucher['benefit']['value'], 100.0)

    def test_product_filtering(self):
        """Verify products are filtered."""
        self.create_coupon(partner=self.partner)
        response = self.client.get(PRODUCT_LIST_PATH)
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertEqual(response_data['count'], 3)

        filtered_url = '{}?product_class=CoUpOn'.format(PRODUCT_LIST_PATH)
        response = self.client.get(filtered_url)
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertEqual(response_data['count'], 1)
        self.assertEqual(response_data['results'][0]['product_class'], COUPON_PRODUCT_CLASS_NAME)
