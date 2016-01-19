"""Contains the tests for publish to lms command."""

import ddt
import logging
import mock
import os
from StringIO import StringIO
import tempfile

from django.core.management import call_command
from django.core.management import CommandError

from ecommerce.courses.models import Course
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.tests.testcases import TransactionTestCase

logger = logging.getLogger(__name__)


@ddt.ddt
class PublishCoursesToLMSTests(TransactionTestCase):
    """Tests the course publish command."""

    tmp_file_path = os.path.join(tempfile.gettempdir(), "tmp-testfile.txt")

    def setUp(self):
        super(PublishCoursesToLMSTests, self).setUp()
        self.course = CourseFactory()
        self.create_course_ids_file(self.course.id)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.tmp_file_path):
            try:
                os.remove(cls.tmp_file_path)
            except:
                logger.error("Error on deleting the temp file {}".format(cls.tmp_file_path))

    def create_course_ids_file(self, course_id):
        """Write the course_id to the temp file."""

        with open(self.tmp_file_path, 'w') as f:
            f.write(course_id)

    @ddt.data("", "fake/path")
    def test_invalid_file_path(self, course_ids_file):
        """ The command should raise CommandError if invalid path is passed. """

        with self.assertRaises(CommandError):
            out = StringIO()
            call_command('publish_to_lms', course_ids_file=course_ids_file, stderr=out)

    def test_invalid_course_id(self):
        """ The course failed due to invalid course id. """

        # Mock the LMS call
        with mock.patch.object(Course, 'publish_to_lms') as mock_publish:
            fake_course_id = "fake_course_id"
            out = StringIO()
            error_msg = "The course {} does not exists.".format(fake_course_id)
            error_str = "Course_id={} Error={}".format(fake_course_id, error_msg)

            self.create_course_ids_file(fake_course_id)
            mock_publish.return_value = None
            call_command('publish_to_lms', course_ids_file=self.tmp_file_path, stderr=out)
            self.assertTrue(error_str in out.getvalue().strip())

    def test_course_publish_successfully(self):
        """ All courses should be published successfully."""

        # Mock the LMS call
        with mock.patch.object(Course, 'publish_to_lms') as mock_publish:
            mock_publish.return_value = None
            out = StringIO()
            call_command('publish_to_lms', course_ids_file=self.tmp_file_path, stderr=out)
            mock_publish.assert_called_once_with()
            self.assertTrue("All Courses published successfully." in out.getvalue().strip())

    def test_course_publish_failed(self):
        """ The course failed to be published."""

        # Mock the LMS call
        with mock.patch.object(Course, 'publish_to_lms') as mock_publish:
            error_msg = "The failure message."
            mock_publish.return_value = error_msg
            out = StringIO()
            call_command('publish_to_lms', course_ids_file=self.tmp_file_path, stderr=out)
            mock_publish.assert_called_once_with()
            self.assertFalse("All Courses published successfully." in out.getvalue().strip())
            error_str = "Course_id={} Error={}".format(self.course.id, error_msg)
            self.assertTrue(error_str in out.getvalue().strip())
