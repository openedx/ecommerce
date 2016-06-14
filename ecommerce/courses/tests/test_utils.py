import ddt
import hashlib
import logging
import mock

from django.conf import settings
from django.core.cache import cache
from django.test import override_settings

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
        seat = course.create_or_update_seat(certificate_type, id_verification_required, 10.00, self.partner)
        self.assertEqual(mode_for_seat(seat), mode)

    # @httpretty.activate
    @override_settings(COURSE_CATALOG_API_URL=COURSE_CATALOG_API_URL)
    # @mock_course_catalog_api_client
    def test_get_course_info(self):
        """ Check to see if course info gets cached """
        with mock.patch('ecommerce.core.models.SiteConfiguration.course_catalog_api_client', mock.PropertyMock(return_value=EdxRestApiClient(
                    settings.COURSE_CATALOG_API_URL,
                    jwt='auth-token'))) as mock_client:
            course = CourseFactory()
            query = 'key={}'.format(course.id)
            log.debug(mock_client.__dict__)
            self.mock_dynamic_catalog_course_runs_api(course_run=course)

            cache_key = 'courses_api_detail_{}'.format(course.id)
            cache_hash = hashlib.md5(cache_key).hexdigest()
            cached_course = cache.get(cache_hash)
            self.assertIsNone(cached_course)

            response = get_course_info(self.site, course.id)
            self.assertEqual(response, course.name)

            cached_course = cache.get(cache_hash)
            self.assertEqual(cached_course, response)
