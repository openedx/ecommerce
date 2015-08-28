from datetime import datetime
from copy import deepcopy
from decimal import Decimal
import json

from django.core.urlresolvers import reverse
from django.test import TestCase
import mock
import pytz
from waffle.models import Switch

from ecommerce.core.constants import ISO_8601_FORMAT
from ecommerce.courses.models import Course
from ecommerce.courses.publishers import LMSPublisher
from ecommerce.extensions.api.v2.tests.views import JSON_CONTENT_TYPE
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.tests.mixins import UserMixin


EXPIRES = datetime(year=1992, month=4, day=24, tzinfo=pytz.utc)
EXPIRES_STRING = EXPIRES.strftime(ISO_8601_FORMAT)


class AtomicPublicationTests(CourseCatalogTestMixin, UserMixin, TestCase):
    def setUp(self):
        super(AtomicPublicationTests, self).setUp()

        self.course_id = 'BadgerX/B101/2015'
        self.course_name = 'Dances with Badgers'
        self.create_path = reverse('api:v2:publication:create')
        self.update_path = reverse('api:v2:publication:update', kwargs={'course_id': self.course_id})
        self.data = {
            'id': self.course_id,
            'name': self.course_name,
            'verification_deadline': EXPIRES_STRING,
            'products': [
                {
                    'product_class': 'Seat',
                    'expires': None,
                    'price': 0.00,
                    'attribute_values': [
                        {
                            'name': 'id_verification_required',
                            'value': False
                        }
                    ]
                },
                {
                    'product_class': 'Seat',
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
                    ]
                },
                {
                    'product_class': 'Seat',
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
                    ]
                },
                {
                    'product_class': 'Seat',
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
                    ]
                }
            ]
        }

        self.user = self.create_user(is_staff=True)
        self.client.login(username=self.user.username, password=self.password)

        self.publication_switch = Switch.objects.create(name='publish_course_modes_to_lms', active=False)

    def _toggle_publication(self, is_enabled):
        """Toggle LMS publication."""
        self.publication_switch.active = is_enabled
        self.publication_switch.save()

    def _purge_courses(self, recreate=False):
        # Delete existing Courses and products so we can retry creation.
        Course.objects.all().delete()

        if recreate:
            # Create a Course.
            course = Course.objects.create(
                id=self.course_id,
                name=self.course_name,
                verification_deadline=EXPIRES,
            )

            # Create associated products.
            for product in self.data['products']:
                attrs = {'certificate_type': ''}
                attrs.update({attr['name']: attr['value'] for attr in product['attribute_values']})

                attrs['expires'] = EXPIRES if product['expires'] else None
                attrs['price'] = Decimal(product['price'])

                course.create_or_update_seat(**attrs)

    def _update_data(self):
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

    def _assert_course_saved(self, course_id, expected=None):
        """Verify that the expected Course and associated products have been saved."""
        if expected is None:
            self.assertFalse(Course.objects.filter(id=course_id).exists())
        else:
            # Verify that Course was saved.
            self.assertTrue(Course.objects.filter(id=course_id).exists())

            course = Course.objects.get(id=course_id)
            self.assertEqual(course.name, expected['name'])

            verification_deadline = EXPIRES if expected.get('verification_deadline') else None
            self.assertEqual(course.verification_deadline, verification_deadline)

            # Validate product structure.
            products = expected['products']
            expected_child_products = len(products)
            expected_parent_products = 1
            self.assertEqual(len(course.products.all()), expected_parent_products + expected_child_products)
            self.assertTrue(len(course.products.filter(structure='child')), expected_child_products)

            # Validate product metadata.
            for product in products:
                certificate_type = ''
                id_verification_required = False

                for attr in product['attribute_values']:
                    name = attr['name']
                    if name == 'certificate_type':
                        certificate_type = attr['value']
                    elif name == 'id_verification_required':
                        id_verification_required = attr['value']

                seat_title = 'Seat in {course_name}'.format(course_name=course.name)

                if certificate_type:
                    seat_title += ' with {certificate_type} certificate'.format(certificate_type=certificate_type)

                if id_verification_required:
                    seat_title += ' (and ID verification)'

                # If the seat does not exist, an error will be raised.
                seat = course.seat_products.get(title=seat_title)

                # Verify product price and expiration time.
                expires = EXPIRES if product['expires'] else None
                self.assertEqual(seat.expires, expires)
                self.assertEqual(seat.stockrecords.first().price_excl_tax, product['price'])

    def test_create(self):
        """Verify that a Course and associated products can be created and published."""
        # If LMS publication is disabled, the view should return a 500 and data should NOT be saved.
        response = self.client.post(self.create_path, json.dumps(self.data), JSON_CONTENT_TYPE)
        self.assertEqual(response.status_code, 500)
        self._assert_course_saved(self.course_id)

        self._toggle_publication(True)

        with mock.patch.object(LMSPublisher, 'publish') as mock_publish:
            # If publication fails, the view should return a 500 and data should NOT be saved.
            mock_publish.return_value = False
            response = self.client.post(self.create_path, json.dumps(self.data), JSON_CONTENT_TYPE)
            self.assertEqual(response.status_code, 500)
            self._assert_course_saved(self.course_id)

            # If publication succeeds, the view should return a 201 and data should be saved.
            mock_publish.return_value = True, None
            response = self.client.post(self.create_path, json.dumps(self.data), JSON_CONTENT_TYPE)
            self.assertEqual(response.status_code, 201)
            self._assert_course_saved(self.course_id, expected=self.data)

    def test_update(self):
        """Verify that a Course and associated products can be updated and published."""
        self._purge_courses(recreate=True)
        updated_data = self._update_data()

        # If LMS publication is disabled, the view should return a 500 and data should NOT be saved.
        response = self.client.put(self.update_path, json.dumps(updated_data), JSON_CONTENT_TYPE)
        self.assertEqual(response.status_code, 500)
        self._assert_course_saved(self.course_id, expected=self.data)

        self._toggle_publication(True)

        with mock.patch.object(LMSPublisher, 'publish') as mock_publish:
            # If publication fails, the view should return a 500 and data should NOT be saved.
            mock_publish.return_value = False
            response = self.client.put(self.update_path, json.dumps(updated_data), JSON_CONTENT_TYPE)
            self.assertEqual(response.status_code, 500)
            self._assert_course_saved(self.course_id, expected=self.data)

            # If publication succeeds, the view should return a 200 and data should be saved.
            mock_publish.return_value = True, None
            response = self.client.put(self.update_path, json.dumps(updated_data), JSON_CONTENT_TYPE)
            self.assertEqual(response.status_code, 200)
            self._assert_course_saved(self.course_id, expected=updated_data)

    def test_invalid_course_id(self):
        """Verify that attempting to save a course with a bad ID yields a 400."""
        self.data['id'] = 'Not an ID'

        response = self.client.post(self.create_path, json.dumps(self.data), JSON_CONTENT_TYPE)
        self.assertEqual(response.status_code, 400)
        self._assert_course_saved(self.course_id)

    def test_invalid_product_class(self):
        """Verify that attempting to save a product with a product class other than 'Seat' yields a 400."""
        self.data['products'][0]['product_class'] = 'Not a Seat'

        response = self.client.post(self.create_path, json.dumps(self.data), JSON_CONTENT_TYPE)
        self.assertEqual(response.status_code, 400)
        self._assert_course_saved(self.course_id)

    def test_incomplete_product_attributes(self):
        """Verify that submitting incomplete product attributes yields a 400."""
        self.data['products'][0]['attribute_values'].pop()

        response = self.client.post(self.create_path, json.dumps(self.data), JSON_CONTENT_TYPE)
        self.assertEqual(response.status_code, 400)
        self._assert_course_saved(self.course_id)

    def test_missing_product_price(self):
        """Verify that submitting product data without a price yields a 400."""
        self.data['products'][0].pop('price')

        response = self.client.post(self.create_path, json.dumps(self.data), JSON_CONTENT_TYPE)
        self.assertEqual(response.status_code, 400)
        self._assert_course_saved(self.course_id)

    def test_verification_deadline_optional(self):
        """Verify that submitting a course verification deadline is optional."""
        self.data.pop('verification_deadline')
        self._toggle_publication(True)

        with mock.patch.object(LMSPublisher, 'publish') as mock_publish:
            mock_publish.return_value = True, None
            response = self.client.post(self.create_path, json.dumps(self.data), JSON_CONTENT_TYPE)
            self.assertEqual(response.status_code, 201)
            self._assert_course_saved(self.course_id, expected=self.data)
