import hashlib
import ddt

from django.conf import settings
from django.core.cache import cache

from ecommerce.core.constants import ENROLLMENT_CODE_SWITCH
from ecommerce.core.tests import toggle_switch
from ecommerce.core.tests.decorators import mock_course_catalog_api_client
from ecommerce.core.tests.patched_httpretty import httpretty
from ecommerce.coupons.tests.mixins import CatalogPreviewMockMixin
from ecommerce.courses.models import Course
from ecommerce.courses.utils import get_course_info, mode_for_seat
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.tests.testcases import TestCase


@ddt.ddt
class UtilsTests(CourseCatalogTestMixin, CatalogPreviewMockMixin, TestCase):
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
        toggle_switch(ENROLLMENT_CODE_SWITCH, True)
        seat = course.create_or_update_seat(certificate_type, id_verification_required, 10.00, self.partner)
        self.assertEqual(mode_for_seat(seat), mode)
        enrollment_code = course.enrollment_code_product
        if enrollment_code:  # We should only have enrollment codes for allowed types
            self.assertEqual(mode_for_seat(enrollment_code), mode)

    @httpretty.activate
    @mock_course_catalog_api_client
    def test_request_nonexistent_course(self):
        """Check that API request does not return results for a course that does not exist yet"""
        course_id = 'course-v1:test+test+test'
        fake_course_url = '{}course_runs/?q={}'.format(
            settings.COURSE_CATALOG_API_URL,
            'key:"{}"'.format(course_id)
        )
        httpretty.register_uri(
            httpretty.GET, fake_course_url,
            body='{"results": []}',
            content_type='application/json'
        )
        cache.clear()
        nonexistent_course_info = get_course_info(self.site, course_id)
        self.assertIsNone(nonexistent_course_info)

        course, _ = self.create_course_and_seat(course_id=course_id)
        query = 'key:"{}"'.format(course.id)
        self.mock_dynamic_catalog_course_runs_api(course_run=course, query=query)

        course_info = get_course_info(self.site, course.id)
        self.assertEqual(course_info['key'], course_id)

    @httpretty.activate
    @mock_course_catalog_api_client
    def test_get_course_info(self):
        """ Check to see if course info gets cached """
        course_id = 'course-v1:test+test+test'
        course, _ = self.create_course_and_seat(course_id=course_id)
        query = 'key:"{}"'.format(course.id)
        self.mock_dynamic_catalog_course_runs_api(course_run=course, query=query)

        cache_key = 'courses_api_detail_{}'.format(course.id)
        cache_hash = hashlib.md5(cache_key).hexdigest()
        cached_course = cache.get(cache_hash)
        self.assertIsNone(cached_course)

        course_info = get_course_info(self.site, course.id)
        self.assertEqual(course_info['title'], course.name)

        cached_course = cache.get(cache_hash)
        self.assertEqual(cached_course, course_info)
