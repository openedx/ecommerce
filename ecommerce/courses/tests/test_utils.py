import hashlib

import ddt
import httpretty

from django.core.cache import cache

from ecommerce.core.url_utils import get_lms_url
from ecommerce.courses.models import Course
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.courses.utils import get_course_info_from_course_catalog, mode_for_seat
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.tests.testcases import TestCase


@httpretty.activate
@ddt.ddt
class UtilsTests(CourseCatalogTestMixin, TestCase):
    @ddt.unpack
    @ddt.data(
        ('', False, 'audit'),
        ('honor', True, 'honor'),
        ('honor', False, 'honor'),
        ('verified', True, 'verified'),
        ('verified', False, 'verified'),
        ('professional', True, 'professional'),
        ('professional', False, 'no-id-professional'),
        ('no-id-professional', False, 'no-id-professional'),
    )
    def test_mode_for_seat(self, certificate_type, id_verification_required, mode):
        """ Verify the correct enrollment mode is returned for a given seat. """
        course = Course.objects.create(id='edx/Demo_Course/DemoX')
        seat = course.create_or_update_seat(certificate_type, id_verification_required, 10.00, self.partner)
        self.assertEqual(mode_for_seat(seat), mode)

    def test_get_course_info_from_course_catalog(self):
        """ Check to see if course info gets cached """
        course = CourseFactory()
        course_url = get_lms_url('api/courses/v1/courses/{}/'.format(course.id))
        httpretty.register_uri(httpretty.GET, course_url, body=course.name, status=200, content_type='application/json')

        cache_key = 'courses_api_detail_{}'.format(course.id)
        cache_hash = hashlib.md5(cache_key).hexdigest()
        cached_course = cache.get(cache_hash)
        self.assertIsNone(cached_course)

        response = get_course_info_from_course_catalog(self.request.site, course.id)
        self.assertEqual(response, course.name)

        cached_course = cache.get(cache_hash)
        self.assertEqual(cached_course, response)
