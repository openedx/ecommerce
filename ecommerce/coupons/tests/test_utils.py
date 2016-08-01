import httpretty

from ecommerce.core.tests.decorators import mock_course_catalog_api_client
from ecommerce.coupons.tests.mixins import CourseCatalogMockMixin, CouponMixin
from ecommerce.coupons.utils import get_seats_from_query
from ecommerce.tests.testcases import TestCase


@httpretty.activate
@mock_course_catalog_api_client
class CouponUtilsTests(CouponMixin, CourseCatalogMockMixin, TestCase):
    def setUp(self):
        super(CouponUtilsTests, self).setUp()
        self.query = 'key:*'
        self.seat_type = 'verified'
        self.course_id = 'course-v1:test+test+test'

    def test_get_seat_from_query(self):
        """ Verify right seat is returned. """
        course, seat = self.create_course_and_seat(course_id=self.course_id)
        self.mock_dynamic_catalog_course_runs_api(query=self.query, course_run=course)
        response = get_seats_from_query(self.site, self.query, self.seat_type)
        self.assertEqual(seat, response[0])

    def test_get_seat_from_query_no_product(self):
        """ Verify an empty list is returned for no matched seats. """
        course, __ = self.create_course_and_seat(seat_type='professional', course_id=self.course_id)
        self.mock_dynamic_catalog_course_runs_api(query=self.query, course_run=course)
        response = get_seats_from_query(self.site, self.query, self.seat_type)
        self.assertEqual(response, [])
