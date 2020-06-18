# encoding: utf-8
"""Contains the tests for publish to lms command."""
import logging
import os
import tempfile

import ddt
import mock
from django.core.management import CommandError, call_command
from testfixtures import LogCapture

from ecommerce.courses.models import Course
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.tests.testcases import TransactionTestCase

logger = logging.getLogger(__name__)
LOGGER_NAME = 'ecommerce.courses.management.commands.publish_to_lms'


@ddt.ddt
class PublishCoursesToLMSTests(DiscoveryTestMixin, TransactionTestCase):
    """Tests the course publish command."""

    tmp_file_path = os.path.join(tempfile.gettempdir(), "tmp-testfile.txt")

    def setUp(self):
        super(PublishCoursesToLMSTests, self).setUp()
        self.partner.default_site = self.site
        self.course = CourseFactory(partner=self.partner)
        self.create_course_ids_file(self.tmp_file_path, [self.course.id])

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.tmp_file_path):
            os.remove(cls.tmp_file_path)

    def create_course_ids_file(self, file_path, course_ids):
        """Write the course_ids list to the temp file."""

        with open(file_path, 'w') as temp_file:
            temp_file.write("\n".join(course_ids))

    @ddt.data("", "fake/path")
    def test_invalid_file_path(self, course_ids_file):
        """ Verify command raises the CommandError for invalid file path. """

        with self.assertRaises(CommandError):
            call_command('publish_to_lms', course_ids_file=course_ids_file)

    def test_invalid_course_id(self):
        """ Verify invalid course_id fails. """

        fake_course_id = "fake_course_id"
        self.create_course_ids_file(self.tmp_file_path, [fake_course_id])
        expected = (
            (
                LOGGER_NAME,
                "INFO",
                "Publishing 1 courses."
            ),
            (
                LOGGER_NAME,
                "ERROR",
                u"(1/1) Failed to publish {}: Course does not exist.".format(fake_course_id)
            ),
            (
                LOGGER_NAME,
                "ERROR",
                "Completed publishing courses. 1 of 1 failed."
            )
        )
        with LogCapture(LOGGER_NAME) as lc:
            call_command('publish_to_lms', course_ids_file=self.tmp_file_path)
            lc.check(*expected)

    def test_course_publish_successfully(self):
        """ Verify all courses are successfully published."""

        second_course = CourseFactory(partner=self.partner)
        self.create_course_ids_file(self.tmp_file_path, [self.course.id, second_course.id])
        expected = (
            (
                LOGGER_NAME,
                "INFO",
                "Publishing 2 courses."
            ),
            (
                LOGGER_NAME,
                "INFO",
                u"(1/2) Successfully published {}.".format(self.course.id)
            ),
            (
                LOGGER_NAME,
                "INFO",
                u"(2/2) Successfully published {}.".format(second_course.id)),
            (
                LOGGER_NAME,
                "INFO",
                "All 2 courses successfully published."
            )
        )
        with mock.patch.object(Course, 'publish_to_lms', autospec=True) as mock_publish:
            mock_publish.return_value = None
            with LogCapture(LOGGER_NAME) as lc:
                call_command('publish_to_lms', course_ids_file=self.tmp_file_path)
                lc.check(*expected)
        # Check that the mocked function was called twice.
        self.assertListEqual(
            mock_publish.call_args_list, [mock.call(self.course), mock.call(second_course)]
        )

    def test_course_publish_failed(self):
        """ Verify failed courses are logged."""

        error_msg = "The failure message."
        expected = (
            (
                LOGGER_NAME,
                "INFO",
                "Publishing 1 courses."
            ),
            (
                LOGGER_NAME,
                "ERROR",
                u"(1/1) Failed to publish {}: {}".format(self.course.id, error_msg)
            ),
            (
                LOGGER_NAME,
                "ERROR",
                "Completed publishing courses. 1 of 1 failed."
            )
        )
        with mock.patch.object(Course, 'publish_to_lms') as mock_publish:
            mock_publish.return_value = error_msg
            with LogCapture(LOGGER_NAME) as lc:
                call_command('publish_to_lms', course_ids_file=self.tmp_file_path)
                lc.check(*expected)
            mock_publish.assert_called_once_with()

    def test_unicode_file_name(self):
        """ Verify the unicode files name are read correctly."""
        unicode_file = os.path.join(tempfile.gettempdir(), u"اول.txt")
        self.create_course_ids_file(unicode_file, [self.course.id])
        expected = (
            (
                LOGGER_NAME,
                "INFO",
                "Publishing 1 courses."
            ),
            (
                LOGGER_NAME,
                "INFO",
                u"(1/1) Successfully published {}.".format(self.course.id)
            ),
            (
                LOGGER_NAME,
                "INFO",
                "All 1 courses successfully published."
            )
        )
        with mock.patch.object(Course, 'publish_to_lms') as mock_publish:
            mock_publish.return_value = None
            with LogCapture(LOGGER_NAME) as lc:
                call_command('publish_to_lms', course_ids_file=unicode_file)
                lc.check(*expected)

        mock_publish.assert_called_once_with()
        os.remove(unicode_file)
