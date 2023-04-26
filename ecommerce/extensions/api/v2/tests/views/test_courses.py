

import json

import mock
from django.contrib.auth import get_user_model
from django.urls import reverse
from oscar.core.loading import get_class, get_model

from ecommerce.core.constants import ISO_8601_FORMAT, SEAT_PRODUCT_CLASS_NAME
from ecommerce.core.tests import toggle_switch
from ecommerce.courses.models import Course
from ecommerce.courses.publishers import LMSPublisher
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.api.v2.tests.views import JSON_CONTENT_TYPE, ProductSerializerMixin
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.tests.mixins import JwtMixin
from ecommerce.tests.testcases import TestCase

Product = get_model('catalogue', 'Product')
ProductClass = get_model('catalogue', 'ProductClass')
Selector = get_class('partner.strategy', 'Selector')
User = get_user_model()


class CourseViewSetTests(JwtMixin, ProductSerializerMixin, DiscoveryTestMixin, TestCase):
    list_path = reverse('api:v2:course-list')

    def setUp(self):
        super(CourseViewSetTests, self).setUp()
        self.user = self.create_user(is_staff=True)
        self.client.login(username=self.user.username, password=self.password)
        self.course = self.create_course()

    def create_course(self):
        return CourseFactory(id='edX/DemoX/Demo_Course', name='Test Course', partner=self.partner)

    def serialize_course(self, course, include_products=False):
        """ Serializes a course to a Python dict. """
        products_url = self.get_full_url(reverse('api:v2:course-product-list',
                                                 kwargs={'parent_lookup_course_id': course.id}))

        last_edited = course.modified.strftime(ISO_8601_FORMAT)
        enrollment_code = course.enrollment_code_product

        data = {
            'id': course.id,
            'name': course.name,
            'verification_deadline': course.verification_deadline,
            'type': course.type,
            'url': self.get_full_url(reverse('api:v2:course-detail', kwargs={'pk': course.id})),
            'products_url': products_url,
            'last_edited': last_edited,
            'has_active_bulk_enrollment_code': bool(enrollment_code)
        }

        if include_products:
            data['products'] = [self.serialize_product(product) for product in course.products.all()]

        return data

    def test_staff_authorization(self):
        """ Verify the endpoint is not accessible to non-staff users. """
        self.client.logout()
        response = self.client.get(self.list_path)
        self.assertEqual(response.status_code, 401)

        user = self.create_user()
        self.client.login(username=user.username, password=self.password)
        response = self.client.get(self.list_path)
        self.assertEqual(response.status_code, 403)

    def test_jwt_authentication(self):
        """ Verify the endpoint supports JWT authentication and user creation. """
        username = 'some-user'
        email = 'some-user@example.com'
        is_staff = True

        auth_header = f'JWT {self.generate_new_user_token(username, email, is_staff)}'
        self.assertFalse(User.objects.filter(username=username).exists())

        response = self.client.get(
            self.list_path,
            HTTP_AUTHORIZATION=auth_header
        )
        self.assertEqual(response.status_code, 200)

        user = User.objects.latest()
        self.assertEqual(user.username, username)
        self.assertEqual(user.email, email)
        self.assertTrue(user.is_staff)

    def test_list(self):
        """ Verify the view returns a list of Courses. """
        CourseFactory()
        self.assertEqual(Course.objects.count(), 2)

        response = self.client.get(self.list_path)
        self.assertEqual(response.status_code, 200)
        self.assertListEqual(response.json()['results'], [self.serialize_course(self.course)])

        # If no Courses exist, the view should return an empty results list.
        Course.objects.all().delete()
        response = self.client.get(self.list_path)
        self.assertDictEqual(response.json(), {'count': 0, 'next': None, 'previous': None, 'results': []})

    def test_create(self):
        """ Verify the view can create a new Course."""
        Course.objects.all().delete()

        course_id = 'edX/DemoX/Demo_Course'
        course_name = 'Test Course'
        data = {
            'id': course_id,
            'name': course_name
        }
        response = self.client.post(self.list_path, json.dumps(data), JSON_CONTENT_TYPE)
        self.assertEqual(response.status_code, 201)

        # Verify Course exists
        course = Course.objects.get(id=course_id)
        self.assertEqual(course.name, course_name)

        # Ensure the parent and child seats were created
        self.assertEqual(course.products.count(), 1)

        # Validate the parent seat
        seat_product_class = ProductClass.objects.get(name=SEAT_PRODUCT_CLASS_NAME)
        parent = course.parent_seat_product
        self.assertEqual(parent.structure, Product.PARENT)
        self.assertEqual(parent.title, 'Seat in Test Course')
        self.assertEqual(parent.get_product_class(), seat_product_class)
        self.assertEqual(parent.attr.course_key, course.id)

    def test_retrieve(self):
        """ Verify the view returns a single course. """
        # The view should return a 404 if the course does not exist.
        path = reverse('api:v2:course-detail', kwargs={'pk': 'aaa/bbb/ccc'})
        response = self.client.get(path)
        self.assertEqual(response.status_code, 404)

        path = reverse('api:v2:course-detail', kwargs={'pk': self.course.id})
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertDictEqual(response.json(), self.serialize_course(self.course))

        # Verify nested products can be included
        response = self.client.get(path + '?include_products=true')
        self.assertEqual(response.status_code, 200)
        self.assertDictEqual(response.json(), self.serialize_course(self.course, include_products=True))

    def test_update(self):
        """ Verify the view updates the information of existing courses. """
        course_id = self.course.id
        path = reverse('api:v2:course-detail', kwargs={'pk': course_id})
        name = 'Something awesome!'
        response = self.client.put(path, json.dumps(
            {'id': course_id, 'name': name}
        ), JSON_CONTENT_TYPE)
        self.assertEqual(response.status_code, 200, response.content)

        # Reload the Course
        self.course = Course.objects.get(id=course_id)
        self.assertEqual(self.course.name, name)
        self.assertDictEqual(response.json(), self.serialize_course(self.course))

    def test_destroy(self):
        """ Verify the view does NOT allow courses to be destroyed. """
        course_id = self.course.id
        path = reverse('api:v2:course-detail', kwargs={'pk': course_id})
        response = self.client.delete(path)
        self.assertEqual(response.status_code, 405)
        self.assertTrue(Course.objects.filter(id=course_id).exists())

    def assert_publish_response(self, response, status_code, msg):
        self.assertEqual(response.status_code, status_code)
        self.assertDictEqual(response.json(), {'status': msg.format(course_id=self.course.id)})

    def test_publish(self):
        """ Verify the view publishes course data to LMS. """
        course_id = self.course.id
        path = reverse('api:v2:course-publish', kwargs={'pk': course_id})

        # Method should return a 500 if the switch is inactive
        toggle_switch('publish_course_modes_to_lms', False)

        response = self.client.post(path)
        msg = 'Course [{course_id}] was not published to LMS ' \
              'because the switch [publish_course_modes_to_lms] is disabled.'
        self.assert_publish_response(response, 500, msg)

        toggle_switch('publish_course_modes_to_lms', True)

        with mock.patch.object(LMSPublisher, 'publish') as mock_publish:
            # If publish fails, return a 500
            mock_publish.return_value = False
            response = self.client.post(path)
            self.assert_publish_response(response, 500, 'An error occurred while publishing [{course_id}] to LMS.')

            # If publish succeeds, return a 200
            mock_publish.return_value = True
            response = self.client.post(path)
            self.assert_publish_response(response, 200, 'Course [{course_id}] was successfully published to LMS.')
