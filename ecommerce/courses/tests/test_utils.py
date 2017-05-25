import hashlib

import ddt
import httpretty
from django.core.cache import cache
from requests.exceptions import ConnectionError

from ecommerce.core.constants import ENROLLMENT_CODE_SWITCH
from ecommerce.core.tests import toggle_switch
from ecommerce.core.tests.decorators import mock_course_catalog_api_client
from ecommerce.coupons.tests.mixins import CourseCatalogMockMixin
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.courses.tests.mixins import CourseCatalogServiceMockMixin
from ecommerce.courses.utils import (
    get_certificate_type_display_value, get_course_catalogs, get_course_info_from_catalog, mode_for_seat
)
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.tests.testcases import TestCase


@httpretty.activate
@ddt.ddt
class UtilsTests(CourseCatalogTestMixin, CourseCatalogMockMixin, TestCase):
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
        course = CourseFactory(id='edx/Demo_Course/DemoX', site=self.site)
        toggle_switch(ENROLLMENT_CODE_SWITCH, True)
        seat = course.create_or_update_seat(certificate_type, id_verification_required, 10.00, self.partner)
        self.assertEqual(mode_for_seat(seat), mode)
        enrollment_code = course.enrollment_code_product
        if enrollment_code:  # We should only have enrollment codes for allowed types
            self.assertEqual(mode_for_seat(enrollment_code), mode)

    @mock_course_catalog_api_client
    def test_get_course_info_from_catalog(self):
        """ Check to see if course info gets cached """
        course = CourseFactory()
        self.mock_dynamic_catalog_single_course_runs_api(course)

        cache_key = 'courses_api_detail_{}{}'.format(course.id, self.site.siteconfiguration.partner.short_code)
        cache_key = hashlib.md5(cache_key).hexdigest()
        cached_course = cache.get(cache_key)
        self.assertIsNone(cached_course)

        response = get_course_info_from_catalog(self.request.site, course)

        self.assertEqual(response['title'], course.name)

        cached_course = cache.get(cache_key)
        self.assertEqual(cached_course, response)

    @ddt.data(
        ('honor', 'Honor'),
        ('verified', 'Verified'),
        ('professional', 'Professional'),
        ('audit', 'Audit')
    )
    @ddt.unpack
    def test_cert_display(self, cert_type, cert_display):
        """ Verify certificate display types. """
        self.assertEqual(get_certificate_type_display_value(cert_type), cert_display)

    def test_cert_display_assertion(self):
        """ Verify assertion for invalid cert type """
        self.assertRaises(ValueError, lambda: get_certificate_type_display_value('junk'))


@ddt.ddt
@httpretty.activate
class GetCourseCatalogUtilTests(CourseCatalogServiceMockMixin, TestCase):

    def tearDown(self):
        # Reset HTTPretty state (clean up registered urls and request history)
        httpretty.reset()

    def _assert_num_requests(self, count):
        """
        DRY helper for verifying request counts.
        """
        self.assertEqual(len(httpretty.httpretty.latest_requests), count)

    def _assert_get_course_catalogs(self, catalog_name_list):
        """
        Helper method to validate the response from the method
        "get_course_catalogs".
        """
        cache_key = '{}.catalog.api.data'.format(self.request.site.domain)
        cache_key = hashlib.md5(cache_key).hexdigest()
        cached_course_catalogs = cache.get(cache_key)
        self.assertIsNone(cached_course_catalogs)

        response = get_course_catalogs(self.request.site)

        self.assertEqual(len(response), len(catalog_name_list))
        for catalog_index, catalog in enumerate(response):
            self.assertEqual(catalog['name'], catalog_name_list[catalog_index])

        cached_course = cache.get(cache_key)
        self.assertEqual(cached_course, response)

    @mock_course_catalog_api_client
    def test_get_course_catalogs_for_single_catalog_with_id(self):
        """
        Verify that method "get_course_catalogs" returns proper response for a
        single catalog by its id.
        """
        self.mock_course_discovery_api_for_catalog_by_resource_id()

        catalog_id = 1
        cache_key = '{}.catalog.api.data.{}'.format(self.request.site.domain, catalog_id)
        cache_key = hashlib.md5(cache_key).hexdigest()
        cached_course_catalog = cache.get(cache_key)
        self.assertIsNone(cached_course_catalog)

        response = get_course_catalogs(self.request.site, catalog_id)
        self.assertEqual(response['name'], 'Catalog {}'.format(catalog_id))

        cached_course = cache.get(cache_key)
        self.assertEqual(cached_course, response)

        # Verify the API was actually hit (not the cache)
        self._assert_num_requests(1)

    @mock_course_catalog_api_client
    @ddt.data(
        ['Catalog 1'],
        ['Catalog 1', 'Catalog 2'],
    )
    def test_get_course_catalogs_for_single_page_api_response(self, catalog_name_list):
        """
        Verify that method "get_course_catalogs" returns proper response for
        single page Course Discovery API response and uses cache to return data
        in case of same API request.
        """
        self.mock_catalog_api(catalog_name_list)

        self._assert_get_course_catalogs(catalog_name_list)

        # Verify the API was hit once
        self._assert_num_requests(1)

        # Now fetch the catalogs again and there should be no more actual call
        # to Course Discovery API as the data will be fetched from the cache
        get_course_catalogs(self.request.site)
        self._assert_num_requests(1)

    @mock_course_catalog_api_client
    def test_get_course_catalogs_for_paginated_api_response(self):
        """
        Verify that method "get_course_catalogs" returns all catalogs for
        paginated Course Discovery API response for multiple catalogs.
        """
        catalog_name_list = ['Catalog 1', 'Catalog 2', 'Catalog 3']
        self.mock_course_discovery_api_for_paginated_catalogs(catalog_name_list)

        self._assert_get_course_catalogs(catalog_name_list)

        # Verify the API was hit for each catalog page
        self._assert_num_requests(len(catalog_name_list))

    @mock_course_catalog_api_client
    def test_get_course_catalogs_for_failure(self):
        """
        Verify that method "get_course_catalogs" raises exception in case
        the Course Discovery API fails to return data.
        """
        exception = ConnectionError
        self.mock_catalog_api_failure(exception)

        with self.assertRaises(exception):
            get_course_catalogs(self.request.site)
