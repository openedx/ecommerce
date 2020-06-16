# encoding: utf-8
"""Contains the tests for enrollment code creation command."""
import logging
import os
import tempfile
from decimal import Decimal

from django.core.management import CommandError, call_command
from testfixtures import LogCapture

from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.tests.testcases import TransactionTestCase

logger = logging.getLogger(__name__)
LOGGER_NAME = 'ecommerce.courses.management.commands.create_enrollment_codes'


class CreateEnrollmentCodesTests(DiscoveryTestMixin, TransactionTestCase):
    """
    Tests the enrollment code creation command.
    """
    tmp_file_path = os.path.join(tempfile.gettempdir(), 'tmp-courses.txt')

    def setUp(self):
        """
        Create test courses and and temp file containing course ids.
        """
        super(CreateEnrollmentCodesTests, self).setUp()
        self.professional_course_1 = self.create_course(seat_type=str('professional'))
        self.professional_course_2 = self.create_course(seat_type=str('professional'))
        self.audit_course = self.create_course(seat_type=str('audit'))
        self.verified_course = self.create_course(seat_type=str('verified'))

        self.create_course_ids_file(
            self.tmp_file_path,
            [self.professional_course_1.id, self.audit_course.id, self.verified_course.id],
        )

    def create_course(self, seat_type='verified'):
        """
        Create a course and a seat for that course.

        Arguments:
            seat_type (str): the seat type

        Returns:
            The created course.
        """
        course = CourseFactory(partner=self.partner)
        course.create_or_update_seat(seat_type, False, Decimal(10.0))
        return course

    @classmethod
    def tearDownClass(cls):
        """
        Remove temporary file.
        """
        if os.path.exists(cls.tmp_file_path):
            os.remove(cls.tmp_file_path)

    @staticmethod
    def create_course_ids_file(file_path, course_ids):
        """
        Write the course_ids list to the temp file.
        """
        with open(file_path, 'w') as temp_file:
            temp_file.write(str("\n".join(course_ids)))

    def test_invalid_file_path(self):
        """
        Verify command raises the CommandError for invalid file path.
        """
        with self.assertRaises(CommandError):
            call_command('create_enrollment_codes', course_ids_file="invalid/courses_id/file/path")

    def test_invalid_course_id(self):
        """
        Verify invalid course_id fails.
        """
        fake_course_id = "fake_course_id"
        self.create_course_ids_file(self.tmp_file_path, [fake_course_id])
        expected = (
            (
                LOGGER_NAME,
                'INFO',
                'Creating enrollment code for 1 courses.'
            ),
            (
                LOGGER_NAME,
                'ERROR',
                '(1/1) Failed to generate enrollment codes for "%s": Course does not exist.' % fake_course_id
            ),
            (
                LOGGER_NAME,
                'ERROR',
                'Completed enrollment codes generation. 1 of 1 failed.'
            ),
            (
                LOGGER_NAME,
                'ERROR',
                '\n'.join(['Failed courses:', fake_course_id])
            ),
        )
        with LogCapture(LOGGER_NAME) as log_capture:
            call_command('create_enrollment_codes', course_ids_file=self.tmp_file_path)
            log_capture.check(*expected)

    def test_create_enrollment_codes_successfully_with_course_ids_file(self):
        """
        Verify enrollment codes are created successfully for all courses given in course ids file.
        """
        expected = (
            (
                LOGGER_NAME,
                'INFO',
                'Creating enrollment code for 3 courses.'
            ),
            (
                LOGGER_NAME,
                'INFO',
                'Enrollment code generated for "%s" course.' % self.professional_course_1.id
            ),
            (
                LOGGER_NAME,
                'INFO',
                'Skipping enrollment code generation for "%s" course. '
                'Because enrollment codes are not allowed for "%s" seat type.' % (self.audit_course.id, 'audit')
            ),
            (
                LOGGER_NAME,
                'INFO',
                'Enrollment code generated for "%s" course.' % self.verified_course.id
            ),
            (
                LOGGER_NAME,
                'INFO',
                'Successfully generated enrollment codes for the batch of 3 courses.'
            )
        )
        with LogCapture(LOGGER_NAME) as log_capture:
            call_command('create_enrollment_codes', course_ids_file=self.tmp_file_path)
            log_capture.check(*expected)

        # Verify that enrollment code is generated for professiona and verified courses
        self.assertIsNotNone(self.professional_course_1.get_enrollment_code())
        self.assertIsNotNone(self.verified_course.get_enrollment_code())

        # Verify that enrollment code is not generated for audit course
        self.assertIsNone(self.audit_course.get_enrollment_code())

    def test_create_enrollment_codes_successfully_with_all_courses(self):
        """
        Verify enrollment codes are created successfully for all courses.
        """
        self.create_course_ids_file(
            self.tmp_file_path,
            [
                self.professional_course_1.id,
                self.professional_course_2.id,
                self.audit_course.id,
                self.verified_course.id,
            ],
        )

        expected = (
            (
                LOGGER_NAME,
                'INFO',
                'Creating enrollment code for 4 courses.'
            ),
            (
                LOGGER_NAME,
                'INFO',
                'Enrollment code generated for "%s" course.' % self.professional_course_1.id
            ),
            (
                LOGGER_NAME,
                'INFO',
                'Enrollment code generated for "%s" course.' % self.professional_course_2.id
            ),
            (
                LOGGER_NAME,
                'INFO',
                'Skipping enrollment code generation for "%s" course. '
                'Because enrollment codes are not allowed for "%s" seat type.' % (self.audit_course.id, 'audit')
            ),
            (
                LOGGER_NAME,
                'INFO',
                'Enrollment code generated for "%s" course.' % self.verified_course.id
            ),
            (
                LOGGER_NAME,
                'INFO',
                'Successfully generated enrollment codes for the batch of 4 courses.'
            )
        )
        with LogCapture(LOGGER_NAME) as log_capture:
            call_command('create_enrollment_codes', course_ids_file=self.tmp_file_path)
            log_capture.check(*expected)

        # Verify that enrollment code is generated for professiona and verified courses
        self.assertIsNotNone(self.professional_course_1.get_enrollment_code())
        self.assertIsNotNone(self.professional_course_2.get_enrollment_code())
        self.assertIsNotNone(self.verified_course.get_enrollment_code())

        # Verify that enrollment code is not generated for audit course
        self.assertIsNone(self.audit_course.get_enrollment_code())

    def test_create_enrollment_codes_when_course_has_multiple_paid_seats(self):
        """
        Verify multiple paid seats for the same course scenario is handled gracefully by the command.
        """
        # emulate multiple seat scenario for a course.
        self.professional_course_1.create_or_update_seat('verified', False, Decimal(10.0))

        self.create_course_ids_file(
            self.tmp_file_path,
            [self.professional_course_1.id],
        )
        expected = (
            (
                LOGGER_NAME,
                'INFO',
                'Creating enrollment code for 1 courses.'
            ),
            (
                LOGGER_NAME,
                'ERROR',
                'Enrollment code generation failed for "%s" course. Because %s' % (
                    self.professional_course_1.id,
                    'Course "%s" has multiple seats eligible for enrollment codes.' % self.professional_course_1.id
                )
            ),
            (
                LOGGER_NAME,
                'ERROR',
                'Completed enrollment codes generation. 1 of 1 failed.'
            ),
            (
                LOGGER_NAME,
                'ERROR',
                '\n'.join(['Failed courses:', self.professional_course_1.id])
            ),
        )
        with LogCapture(LOGGER_NAME) as log_capture:
            call_command('create_enrollment_codes', course_ids_file=self.tmp_file_path)
            log_capture.check(*expected)

        # Verify that enrollment code is not generated for a course that has multiple seats.
        self.assertIsNone(self.professional_course_1.get_enrollment_code())

    def test_create_enrollment_codes_skips_courses_with_already_an_enrollment_code(self):
        """
        Verify courses with existing enrollment codes are skipped.
        """
        # Delete some courses.
        self.verified_course.delete()
        self.audit_course.delete()
        self.professional_course_2.delete()

        # Create enrollment codes.
        call_command('create_enrollment_codes')

        expected = (
            (
                LOGGER_NAME,
                'INFO',
                'Creating enrollment code for 1 courses.'
            ),
            (
                LOGGER_NAME,
                'INFO',
                'Skipping enrollment code generation for "%s" '
                'course due to existing enrollment codes.' % self.professional_course_1.id
            ),
            (
                LOGGER_NAME,
                'INFO',
                'Successfully generated enrollment codes for the batch of 1 courses.'
            )
        )
        with LogCapture(LOGGER_NAME) as log_capture:
            call_command('create_enrollment_codes')
            log_capture.check(*expected)

        # Verify that enrollment code exists in the database.
        self.assertIsNotNone(self.professional_course_1.get_enrollment_code())

    def test_create_enrollment_codes_with_course_info_errors(self):
        """
        Verify proper info messages are logged when courses do not have required info.
        """
        # emulate multiple seat scenario for a course.
        self.professional_course_1.create_or_update_seat('verified', False, Decimal(10.0))

        # Delete some courses.
        self.audit_course.delete()
        self.verified_course.delete()
        self.professional_course_2.delete()

        expected = (
            (
                LOGGER_NAME,
                'INFO',
                'Creating enrollment code for 1 courses.'
            ),
            (
                LOGGER_NAME,
                'ERROR',
                'Enrollment code generation failed for "%s" course. Because %s' % (
                    self.professional_course_1.id,
                    'Course "%s" has multiple seats eligible for enrollment codes.' % self.professional_course_1.id
                )
            ),
            (
                LOGGER_NAME,
                'ERROR',
                'Completed enrollment codes generation. 1 of 1 failed.'
            ),
            (
                LOGGER_NAME,
                'ERROR',
                '\n'.join(['Failed courses:', self.professional_course_1.id])
            ),
        )
        with LogCapture(LOGGER_NAME) as log_capture:
            call_command('create_enrollment_codes')
            log_capture.check(*expected)

        # Verify that enrollment code is not generated for a course that has multiple seats.
        self.assertIsNone(self.professional_course_1.get_enrollment_code())
