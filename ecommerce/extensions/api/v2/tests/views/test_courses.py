from __future__ import unicode_literals
import json

from django.core.urlresolvers import reverse
from django.test import TestCase
import mock
from oscar.core.loading import get_model, get_class
from waffle import Switch

from ecommerce.courses.models import Course
from ecommerce.courses.publishers import LMSPublisher
from ecommerce.extensions.api.v2.tests.views import JSON_CONTENT_TYPE, TestServerUrlMixin
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.tests.mixins import UserMixin

Product = get_model('catalogue', 'Product')
ProductClass = get_model('catalogue', 'ProductClass')
Selector = get_class('partner.strategy', 'Selector')


class CourseViewSetTests(TestServerUrlMixin, CourseCatalogTestMixin, UserMixin, TestCase):
    maxDiff = None
    list_path = reverse('api:v2:course-list')

    def setUp(self):
        super(CourseViewSetTests, self).setUp()
        self.user = self.create_user(is_staff=True)
        self.client.login(username=self.user.username, password=self.password)
        self.course = self.create_course()

    def create_course(self):
        return Course.objects.create(id='edX/DemoX/Demo_Course', name='Test Course')

    def serialize_course(self, course):
        """ Serializes a course to a Python dict. """
        products_url = self.get_full_url(reverse('api:v2:course-product-list',
                                                 kwargs={'parent_lookup_course_id': course.id}))
        return {
            'id': course.id,
            'name': course.name,
            'type': course.type,
            'url': self.get_full_url(reverse('api:v2:course-detail', kwargs={'pk': course.id})),
            'products_url': products_url,
        }

    def test_list(self):
        """ Verify the view returns a list of Courses. """
        response = self.client.get(self.list_path)
        self.assertEqual(response.status_code, 200)
        self.assertListEqual(json.loads(response.content)['results'], [self.serialize_course(self.course)])

        # If no Courses exist, the view should return an empty results list.
        Course.objects.all().delete()
        response = self.client.get(self.list_path)
        self.assertDictEqual(json.loads(response.content), {'count': 0, 'next': None, 'previous': None, 'results': []})

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
        seat_product_class = ProductClass.objects.get(slug='seat')
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
        self.assertDictEqual(json.loads(response.content), self.serialize_course(self.course))

    def test_update(self):
        """ Verify the view updates the information of existing courses. """
        course_id = self.course.id
        path = reverse('api:v2:course-detail', kwargs={'pk': course_id})
        name = 'Something awesome!'
        response = self.client.put(path, json.dumps({'id': course_id, 'name': name}), JSON_CONTENT_TYPE)
        self.assertEqual(response.status_code, 200, response.content)

        # Reload the Course
        self.course = Course.objects.get(id=course_id)
        self.assertEqual(self.course.name, name)
        self.assertDictEqual(json.loads(response.content), self.serialize_course(self.course))

    def test_destroy(self):
        """ Verify the view does NOT allow courses to be destroyed. """
        course_id = self.course.id
        path = reverse('api:v2:course-detail', kwargs={'pk': course_id})
        response = self.client.delete(path)
        self.assertEqual(response.status_code, 405)
        self.assertTrue(Course.objects.filter(id=course_id).exists())

    def assert_publish_response(self, response, status_code, msg):
        self.assertEqual(response.status_code, status_code)
        self.assertDictEqual(json.loads(response.content), {'status': msg.format(course_id=self.course.id)})

    def test_publish(self):
        """ Verify the view publishes course data to LMS. """
        course_id = self.course.id
        path = reverse('api:v2:course-publish', kwargs={'pk': course_id})

        # Method should return a 500 if the switch is inactive
        switch, _created = Switch.objects.get_or_create(name='publish_course_modes_to_lms', active=False)
        response = self.client.post(path)
        msg = 'Course [{course_id}] was not published to LMS ' \
              'because the switch [publish_course_modes_to_lms] is disabled.'
        self.assert_publish_response(response, 500, msg)

        switch.active = True
        switch.save()

        with mock.patch.object(LMSPublisher, 'publish') as mock_publish:
            # If publish fails, return a 500
            mock_publish.return_value = False
            response = self.client.post(path)
            self.assert_publish_response(response, 500, 'An error occurred while publishing [{course_id}] to LMS.')

            # If publish succeeds, return a 200
            mock_publish.return_value = True
            response = self.client.post(path)
            self.assert_publish_response(response, 200, 'Course [{course_id}] was successfully published to LMS.')
