

import json
from copy import deepcopy
from datetime import datetime
from decimal import Decimal

import mock
import pytz
from django.conf import settings
from django.urls import reverse
from oscar.core.loading import get_model

from ecommerce.core.constants import (
    COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME,
    ENROLLMENT_CODE_PRODUCT_CLASS_NAME,
    ISO_8601_FORMAT,
    SEAT_PRODUCT_CLASS_NAME
)
from ecommerce.core.tests import toggle_switch
from ecommerce.courses.models import Course
from ecommerce.courses.publishers import LMSPublisher
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.entitlements.utils import create_or_update_course_entitlement
from ecommerce.extensions.api.v2.tests.views import JSON_CONTENT_TYPE
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.tests.testcases import TestCase

Product = get_model('catalogue', 'Product')
ProductClass = get_model('catalogue', 'ProductClass')

EXPIRES = datetime(year=1992, month=4, day=24, tzinfo=pytz.utc)
EXPIRES_STRING = EXPIRES.strftime(ISO_8601_FORMAT)


class AtomicPublicationTests(DiscoveryTestMixin, TestCase):
    def setUp(self):
        super(AtomicPublicationTests, self).setUp()

        self.course_id = 'BadgerX/B101/2015'
        self.course_uuid = '394a5ce5-6ff4-4b2b-bea1-a273c6920ae1'
        self.course_name = 'Dances with Badgers'
        self.create_path = reverse('api:v2:publication:create')
        self.update_path = reverse('api:v2:publication:update', kwargs={'course_id': self.course_id})
        self.data = {
            'id': self.course_id,
            'uuid': self.course_uuid,
            'name': self.course_name,
            'verification_deadline': EXPIRES_STRING,
            'products': [
                {
                    'product_class': SEAT_PRODUCT_CLASS_NAME,
                    'expires': None,
                    'price': 0.00,
                    'attribute_values': [
                        {
                            'name': 'id_verification_required',
                            'value': False
                        }
                    ],
                    'course': {
                        'honor_mode': True,
                        'id': self.course_id,
                        'name': self.course_name,
                        'type': 'verified',
                        'verification_deadline': None
                    }
                },
                {
                    'product_class': SEAT_PRODUCT_CLASS_NAME,
                    'expires': None,
                    'price': 0.00,
                    'attribute_values': [
                        {
                            'name': 'certificate_type',
                            'value': 'honor'
                        },
                        {
                            'name': 'id_verification_required',
                            'value': False
                        }
                    ],
                    'course': {
                        'honor_mode': True,
                        'id': self.course_id,
                        'name': self.course_name,
                        'type': 'verified',
                        'verification_deadline': None
                    }
                },
                {
                    'product_class': SEAT_PRODUCT_CLASS_NAME,
                    'expires': EXPIRES_STRING,
                    'price': 10.00,
                    'attribute_values': [
                        {
                            'name': 'certificate_type',
                            'value': 'verified'
                        },
                        {
                            'name': 'id_verification_required',
                            'value': True
                        }
                    ],
                    'course': {
                        'honor_mode': True,
                        'id': self.course_id,
                        'name': self.course_name,
                        'type': 'verified',
                        'verification_deadline': None
                    }
                },
                {
                    'product_class': SEAT_PRODUCT_CLASS_NAME,
                    'expires': EXPIRES_STRING,
                    'price': 100.00,
                    'attribute_values': [
                        {
                            'name': 'certificate_type',
                            'value': 'credit'
                        },
                        {
                            'name': 'id_verification_required',
                            'value': True
                        },
                        {
                            'name': 'credit_provider',
                            'value': 'Harvard'
                        },
                        {
                            'name': 'credit_hours',
                            'value': 1
                        }
                    ],
                    'course': {
                        'honor_mode': True,
                        'id': self.course_id,
                        'name': self.course_name,
                        'type': 'verified',
                        'verification_deadline': None
                    }
                },
                {
                    'product_class': COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME,
                    'price': 50.00,
                    'attribute_values': [
                        {
                            'name': 'certificate_type',
                            'value': 'verified'
                        },
                    ]
                },
            ]
        }

        self.user = self.create_user(is_staff=True, username=settings.DISCOVERY_WORKER_USERNAME)
        self.client.login(username=self.user.username, password=self.password)

        self.publication_switch = toggle_switch('publish_course_modes_to_lms', True)

    def _toggle_publication(self, is_enabled):
        """Toggle LMS publication."""
        self.publication_switch.active = is_enabled
        self.publication_switch.save()

    def create_course_and_seats(self):
        # Delete existing Courses and products so we can retry creation.
        Course.objects.all().delete()

        # Create a Course.
        course = CourseFactory(
            id=self.course_id,
            name=self.course_name,
            verification_deadline=EXPIRES,
            partner=self.partner
        )

        # Create associated products.
        for product in self.data['products']:
            attrs = {'certificate_type': ''}
            attrs.update({attr['name']: attr['value'] for attr in product['attribute_values']})

            if product['product_class'] == COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME:
                create_or_update_course_entitlement(
                    attrs['certificate_type'],
                    Decimal(product['price']),
                    self.partner,
                    self.course_uuid,
                    course.name,
                )
            else:
                attrs['expires'] = EXPIRES if product['expires'] else None
                attrs['price'] = Decimal(product['price'])
                seat = course.create_or_update_seat(**attrs)
                # The stockrecord partner sku is used for updates
                product['stockrecords'] = [{'partner_sku': seat.stockrecords.first().partner_sku}]

    def generate_update_payload(self):
        """ Returns dictionary representing the data payload sent for an update request. """
        updated_data = deepcopy(self.data)
        for product in updated_data['products']:
            attrs = {attr['name']: attr['value'] for attr in product['attribute_values']}

            # Update the price of the verified seat.
            if attrs.get('certificate_type') == 'verified':
                product['price'] = 20.00

        updated_data['name'] = 'A New Name'

        # Strip course_id, which should be absent from PUT requests.
        updated_data.pop('id')
        return updated_data

    def assert_course_does_not_exist(self, course_id):
        """  Verify no Course with the specified ID exists."""
        self.assertFalse(Course.objects.filter(id=course_id).exists())

    def assert_entitlement_saved(self, course, expected):
        certificate_type = None
        for attr in expected['attribute_values']:
            name = attr['name']
            if name == 'certificate_type':
                certificate_type = attr['value']
        self.assertIsNotNone(certificate_type)

        # If the seat does not exist, an error will be raised.
        entitlement = Product.objects.get(title='Course {}'.format(course.name))

        self.assertEqual(entitlement.structure, Product.CHILD)
        self.assertEqual(entitlement.parent.product_class.name, COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME)
        self.assertEqual(entitlement.attr.certificate_type, certificate_type)
        self.assertEqual(entitlement.attr.UUID, self.course_uuid)
        self.assertEqual(entitlement.stockrecords.get(partner=self.partner).price_excl_tax, expected['price'])

    def assert_seat_saved(self, course, expected):
        certificate_type = ''

        for attr in expected['attribute_values']:
            name = attr['name']
            if name == 'certificate_type':
                certificate_type = attr['value']

        seat_title = 'Seat in {course_name}'.format(course_name=course.name)

        if certificate_type:
            seat_title += ' with {certificate_type} certificate'.format(certificate_type=certificate_type)

        # If the seat does not exist, an error will be raised.
        seat = course.seat_products.get(title=seat_title)

        # Verify product price and expiration time.
        expires = EXPIRES if expected['expires'] else None
        self.assertEqual(seat.expires, expires)
        self.assertEqual(seat.stockrecords.get(partner=self.partner).price_excl_tax, expected['price'])

        return seat

    def assert_course_saved(self, course_id, expected, enrollment_code_count=0):
        """Verify that the expected Course and associated products have been saved."""
        # Verify that Course was saved.
        self.assertTrue(Course.objects.filter(id=course_id).exists())

        course = Course.objects.get(id=course_id)
        self.assertEqual(course.name, expected['name'])

        verification_deadline = EXPIRES if expected.get('verification_deadline') else None
        self.assertEqual(course.verification_deadline, verification_deadline)

        # Validate seat product structure.
        products = expected['products']
        expected_child_products = len(products)
        expected_parent_products = 2  # entitlement and seat
        self.assertEqual(
            len(Product.objects.all()),
            expected_parent_products + expected_child_products + enrollment_code_count
        )
        self.assertEqual(len(Product.objects.filter(structure='child')), expected_child_products)

        # Validate product metadata.
        for product in products:
            if product['product_class'] == COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME:
                self.assert_entitlement_saved(course, product)
            else:
                self.assert_seat_saved(course, product)

    def test_lms_publication_disabled(self):
        """ Verify the endpoint returns an error, and does not save the course, if publication is disabled. """
        # Disable publication
        self.publication_switch.active = False
        self.publication_switch.save()

        response = self.client.post(self.create_path, json.dumps(self.data), JSON_CONTENT_TYPE)
        self.assertEqual(response.status_code, 500)
        self.assert_course_does_not_exist(self.course_id)

        expected = u'Course [{}] was not published to LMS because the switch [publish_course_modes_to_lms] is ' \
                   u'disabled. To avoid ghost SKUs, data has not been saved.'.format(self.course_id)
        self.assertEqual(response.data.get('error'), expected)

    def test_create(self):
        """Verify that a Course and associated products can be created and published."""
        with mock.patch.object(LMSPublisher, 'publish') as mock_publish:
            # If publication fails, the view should return a 500 and data should NOT be saved.
            error_msg = 'Test publication failed.'
            mock_publish.return_value = error_msg
            response = self.client.post(self.create_path, json.dumps(self.data), JSON_CONTENT_TYPE)

            self.assertEqual(response.status_code, 500)
            self.assert_course_does_not_exist(self.course_id)
            self.assertEqual(response.data.get('error'), error_msg)

            # If publication succeeds, the view should return a 201 and data should be saved.
            mock_publish.return_value = None
            response = self.client.post(self.create_path, json.dumps(self.data), JSON_CONTENT_TYPE)
            self.assertEqual(response.status_code, 201)
            self.assert_course_saved(self.course_id, expected=self.data, enrollment_code_count=1)
            self.assertTrue(Product.objects.filter(product_class__name=ENROLLMENT_CODE_PRODUCT_CLASS_NAME).exists())

    def test_update(self):
        """Verify that a Course and associated products can be updated and published."""
        self.create_course_and_seats()
        updated_data = self.generate_update_payload()

        with mock.patch.object(LMSPublisher, 'publish') as mock_publish:
            # If publication fails, the view should return a 500 and data should NOT be saved.
            error_msg = 'Test publication failed.'
            mock_publish.return_value = error_msg
            response = self.client.put(self.update_path, json.dumps(updated_data), JSON_CONTENT_TYPE)
            self.assertEqual(response.status_code, 500)
            self.assertEqual(response.data.get('error'), error_msg)
            self.assert_course_saved(self.course_id, expected=self.data)

            # If publication succeeds, the view should return a 200 and data should be saved.
            mock_publish.return_value = None
            response = self.client.put(self.update_path, json.dumps(updated_data), JSON_CONTENT_TYPE)
            self.assertEqual(response.status_code, 200)
            self.assert_course_saved(self.course_id, expected=updated_data, enrollment_code_count=1)

    def test_sku_returned(self):
        """Verify that the newly created product SKU is returned in the response."""
        with mock.patch.object(LMSPublisher, 'publish') as mock_publish:
            mock_publish.return_value = None
            response = self.client.post(self.create_path, json.dumps(self.data), JSON_CONTENT_TYPE)

        self.assertEqual(response.status_code, 201)

        seat = self.assert_seat_saved(Course.objects.first(), self.data['products'][0])
        record = seat.stockrecords.first()
        self.assertEqual(response.data['products'][0]['partner_sku'], record.partner_sku)

    def test_invalid_course_id(self):
        """Verify that attempting to save a course with a bad ID yields a 400."""
        self.data['id'] = 'Not an ID'

        response = self.client.post(self.create_path, json.dumps(self.data), JSON_CONTENT_TYPE)
        self.assertEqual(response.status_code, 400)
        self.assert_course_does_not_exist(self.course_id)

    def test_missing_course_uuid(self):
        """Verify that attempting to save a course without a UUID yields a 400."""
        self.data.pop('uuid')

        response = self.client.post(self.create_path, json.dumps(self.data), JSON_CONTENT_TYPE)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.data.get('error'),
            u'You need to provide a course UUID to create Course Entitlements.'
        )
        self.assert_course_does_not_exist(self.course_id)

    def test_missing_course_uuid_without_entitlements(self):
        """Verify that attempting to save a course without a UUID but no entitlements is fine."""
        self.data.pop('uuid')
        self.data['products'] = [x for x in self.data['products'] if x['product_class'] == SEAT_PRODUCT_CLASS_NAME]
        self._post_create_request()

    def test_invalid_course_uuid(self):
        """Verify that attempting to save a course with a bad UUID yields a 400."""
        self.data['uuid'] = 'foo-bar'

        response = self.client.post(self.create_path, json.dumps(self.data), JSON_CONTENT_TYPE)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            str(response.data.get('uuid')[0]), 'Must be a valid UUID.')
        self.assert_course_does_not_exist(self.course_id)

    def test_invalid_product_class(self):
        """Verify that attempting to save a product with a product class other than 'Seat' yields a 400."""
        product_class = 'Not a Seat'
        self.data['products'][0]['product_class'] = product_class

        response = self.client.post(self.create_path, json.dumps(self.data), JSON_CONTENT_TYPE)
        self.assertEqual(response.status_code, 400)
        self.assert_course_does_not_exist(self.course_id)

        self.assertEqual(
            response.data.get('products')[0],
            u'Invalid product class [{product_class}] requested.'.format(product_class=product_class)
        )

    def test_incomplete_seat_attributes(self):
        """Verify that submitting incomplete product attributes yields a 400."""
        for product in self.data['products']:
            if product['product_class'] == SEAT_PRODUCT_CLASS_NAME:
                product['attribute_values'].pop()
                break

        response = self.client.post(self.create_path, json.dumps(self.data), JSON_CONTENT_TYPE)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data.get('products')[0],
            u'Products must indicate whether ID verification is required.'
        )
        self.assert_course_does_not_exist(self.course_id)

    def test_incomplete_entitlement_attributes(self):
        """Verify that submitting incomplete product attributes yields a 400."""
        for product in self.data['products']:
            if product['product_class'] == COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME:
                product['attribute_values'].pop()
                break

        response = self.client.post(self.create_path, json.dumps(self.data), JSON_CONTENT_TYPE)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data.get('products')[0],
            u'Products must have a certificate type.'
        )
        self.assert_course_does_not_exist(self.course_id)

    def test_missing_seat_price(self):
        """Verify that submitting seat data without a price yields a 400."""
        for product in self.data['products']:
            if product['product_class'] == SEAT_PRODUCT_CLASS_NAME:
                product.pop('price')
                break

        response = self.client.post(self.create_path, json.dumps(self.data), JSON_CONTENT_TYPE)
        self.assertEqual(response.status_code, 400)

        self.assertEqual(
            response.data.get('products')[0],
            u'Products must have a price.'
        )
        self.assert_course_does_not_exist(self.course_id)

    def test_missing_entitlement_price(self):
        """Verify that submitting entitlement data without a price yields a 400."""
        for product in self.data['products']:
            if product['product_class'] == COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME:
                product.pop('price')
                break

        response = self.client.post(self.create_path, json.dumps(self.data), JSON_CONTENT_TYPE)
        self.assertEqual(response.status_code, 400)

        self.assertEqual(
            response.data.get('products')[0],
            u'Products must have a price.'
        )
        self.assert_course_does_not_exist(self.course_id)

    def _post_create_request(self):
        """Send a successful POST request to the publish create endpoint."""
        with mock.patch.object(LMSPublisher, 'publish') as mock_publish:
            mock_publish.return_value = None
            response = self.client.post(self.create_path, json.dumps(self.data), JSON_CONTENT_TYPE)
            self.assertEqual(response.status_code, 201)

    def test_verification_deadline_optional(self):
        """Verify that submitting a course verification deadline is optional."""
        self.data.pop('verification_deadline')
        self._toggle_publication(True)

        self._post_create_request()
        self.assert_course_saved(self.course_id, expected=self.data, enrollment_code_count=1)

    def test_create_enrollment_code(self):
        """Verify an enrollment code is created."""
        self._post_create_request()

        course = Course.objects.get(id=self.course_id)
        enrollment_code = course.get_enrollment_code()
        self.assertIsNotNone(enrollment_code)
        self.assertEqual(enrollment_code.expires, EXPIRES)
