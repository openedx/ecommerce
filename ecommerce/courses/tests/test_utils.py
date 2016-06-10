import ddt
import hashlib
import logging
import mock

from django.conf import settings
from django.core.cache import cache
from django.test import override_settings

from ecommerce.core.constants import ENROLLMENT_CODE_SWITCH
from ecommerce.core.tests import toggle_switch

from ecommerce.core.tests.decorators import mock_course_catalog_api_client
from ecommerce.core.tests.patched_httpretty import httpretty
from ecommerce.core.url_utils import get_lms_url
from ecommerce.coupons.tests.mixins import CatalogPreviewMockMixin
from ecommerce.courses.models import Course
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.courses.utils import get_course_info, mode_for_seat
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.tests.testcases import TestCase

from edx_rest_api_client.client import EdxRestApiClient

log = logging.getLogger(__name__)
COURSE_CATALOG_API_URL = 'https://catalog.example.com/api/v1/'

@httpretty.activate
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
    @override_settings(COURSE_CATALOG_API_URL=COURSE_CATALOG_API_URL)
    @mock_course_catalog_api_client
    def test_get_course_info(self):
        """ Check to see if course info gets cached """
        course = CourseFactory()
        query = 'key={}'.format(course.id)
        #self.mock_dynamic_catalog_course_runs_api(course_run=course)

        course_run_url = '{}course_runs/{}'.format(
            settings.COURSE_CATALOG_API_URL,
            # query if query else 'id:course*'
            course.id
        )
        log.debug("URL %s JSON %s", course_run_url, '{"foo": "bar"}')
        httpretty.register_uri(
            httpretty.GET, course_run_url,
            body=course.name,
            content_type='application/json',
            status=200
        )

        cache_key = 'courses_api_detail_{}'.format(course.id)
        cache_hash = hashlib.md5(cache_key).hexdigest()
        cached_course = cache.get(cache_hash)
        self.assertIsNone(cached_course)

        client_get_url = 'https://catalog.example.com/api/v1/course_runs/{}'.format(course.id)
        log.debug('Trying to hit this URL {}'.format(client_get_url))
        self.assertEqual(client_get_url, course_run_url)

        response = get_course_info(self.site, course.id)
        # response = self.site.siteconfiguration.course_catalog_api_client.course_runs(course.id)._store['base_url']
        self.assertEqual(response, course.name)
        #response = self.client.get(client_get_url)

        cached_course = cache.get(cache_hash)
        self.assertEqual(cached_course, response)
