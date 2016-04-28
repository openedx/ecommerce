import json
import datetime

from dateutil.parser import parse
import ddt
import httpretty

from ecommerce.core.url_utils import get_lms_url
from ecommerce.courses.models import Course
from ecommerce.courses.utils import mode_for_seat, get_default_seat_upgrade_deadline
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.tests.testcases import TestCase
from ecommerce.courses.tests.factories import CourseFactory


@ddt.ddt
class UtilsTests(CourseCatalogTestMixin, TestCase):
    def setUp(self):
        super(UtilsTests, self).setUp()
        self.course = CourseFactory()

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

    def mock_courses_api(self, status, body=None):
        """ Mock Courses API with specific status and body. """
        self.assertTrue(httpretty.is_enabled(), 'httpretty must be enabled to mock Course API calls.')

        body = body or {}
        course_url = get_lms_url('api/courses/v1/courses/{}/'.format(self.course))
        httpretty.register_uri(
            httpretty.GET,
            course_url,
            status=status,
            body=json.dumps(body),
            content_type='application/json'
        )

    @httpretty.activate
    @ddt.data(
        datetime.datetime(1990, 1, 1).isoformat(),
        datetime.datetime.today().isoformat(),
        datetime.datetime(2100, 1, 1).isoformat(),
        None
    )
    def test_get_default_seat_upgrade_deadline(self, course_end_date):
        """
        """
        self.mock_courses_api(status=200, body={'end': course_end_date})
        expected_upgrade_deadline = None

        # If course has end date, then the expected upgrade deadline will be 10 before that date.
        if course_end_date:
            expected_upgrade_deadline = parse(course_end_date) - datetime.timedelta(days=10)

        # Verify the method returned expected default deadline.
        default_deadline = get_default_seat_upgrade_deadline(self.course.id)
        self.assertEqual(expected_upgrade_deadline, default_deadline)
