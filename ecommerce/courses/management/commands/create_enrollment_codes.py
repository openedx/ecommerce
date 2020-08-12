"""
This command generates enrollment codes for courses.
"""


import logging
import os

from django.core.management import BaseCommand, CommandError

from ecommerce.core.constants import ENROLLMENT_CODE_SEAT_TYPES
from ecommerce.courses.models import Course

logger = logging.getLogger(__name__)


class CourseInfoError(Exception):
    """
    Raised when course does not have all the required data.
    """


class Command(BaseCommand):
    """
    Creates enrollment codes for courses.
    """

    help = 'Create enrollment codes for courses.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--course-ids-file',
            action='store',
            dest='course_ids_file',
            default=None,
            help='Path of the file to read courses id from.',
            type=str,
        )
        parser.add_argument(
            '--batch-limit',
            action='store',
            dest='batch_limit',
            default=100,
            help='Number of courses in each batch of enrollment code creation.',
            type=int,
        )

    def handle(self, *args, **options):
        course_ids_file = options['course_ids_file']
        batch_limit = options['batch_limit']

        if course_ids_file:
            if not os.path.exists(course_ids_file):
                raise CommandError('Pass the correct absolute path to course ids file as --course_ids_file argument.')

            total_courses, failed_courses = self._generate_enrollment_codes_from_file(course_ids_file)
        else:
            total_courses, failed_courses = self._generate_enrollment_codes_from_db(batch_limit)

        if failed_courses:
            logger.error('Completed enrollment codes generation. %d of %d failed.', len(failed_courses), total_courses)
            logger.error('\n'.join(['Failed courses:'] + failed_courses))
        else:
            logger.info('Successfully generated enrollment codes for the batch of %s courses.', total_courses)

    def _generate_enrollment_codes_from_db(self, batch_limit):
        """
        Generate enrollment codes for the course.

        Arguments:
            batch_limit (int): How many courses to fetch from db to process in each batch.

        Returns:
            (total_course, failed_course): a tuple containing count of course processed and a list containing ids of
                courses whose enrollment codes could not be generated.
        """
        failed_courses = []
        total_courses = 0

        courses = Course.objects.all()[0:batch_limit]
        while courses:
            total_courses += len(courses)
            logger.info('Creating enrollment code for %d courses.', courses.count())

            for course in courses:
                try:
                    self._generate_enrollment_code(course)
                except CourseInfoError as error:
                    logger.error(
                        'Enrollment code generation failed for "%s" course. Because %s',
                        course.id,
                        str(error),
                    )
                    failed_courses.append(course.id)

            courses = Course.objects.all()[total_courses:total_courses + batch_limit]
        return total_courses, failed_courses

    def _generate_enrollment_codes_from_file(self, course_ids_file):
        """
        Generate enrollment codes for the course provided in the course ids file.

        Arguments:
            course_ids_file (str): path of the file containing course ids.

        Returns:
            (total_course, failed_course): a tuple containing count of course processed and a list containing ids of
                courses whose enrollment codes could not be generated.
        """
        failed_courses = []

        with open(course_ids_file, 'r') as file_handler:
            course_ids = file_handler.readlines()
            total_courses = len(course_ids)
            logger.info('Creating enrollment code for %d courses.', total_courses)
            for index, course_id in enumerate(course_ids, start=1):
                try:
                    course_id = course_id.strip()
                    course = Course.objects.get(id=course_id)
                    self._generate_enrollment_code(course)
                except Course.DoesNotExist:
                    failed_courses.append(course_id)
                    logger.error(
                        '(%d/%d) Failed to generate enrollment codes for "%s": Course does not exist.',
                        index,
                        total_courses,
                        course_id
                    )
                except CourseInfoError as error:
                    logger.error(
                        'Enrollment code generation failed for "%s" course. Because %s',
                        course.id,
                        str(error),
                    )
                    failed_courses.append(course.id)
        return total_courses, failed_courses

    def _generate_enrollment_code(self, course):
        """
        Generate enrollment code for the given course.

        Enrollment code is generated if
            1. The course has a course mode that supports enrollment codes AND
            2. The course does not already have an enrollment code for that course mode.

        Arguments:
            course (Course): E-Commerce course object.
        """
        if self.is_course_eligible_for_enrollment_code(course) and not course.get_enrollment_code():
            seat_type, price, id_verification_required = self.get_course_info(course)
            course._create_or_update_enrollment_code(  # pylint: disable=protected-access
                seat_type=seat_type,
                id_verification_required=id_verification_required,
                partner=course.partner,
                price=price,
                expires=None
            )
            logger.info('Enrollment code generated for "%s" course.', course.id)
        elif self.is_course_eligible_for_enrollment_code(course) and course.get_enrollment_code():
            logger.info(
                'Skipping enrollment code generation for "%s" course due to existing enrollment codes.',
                course.id,
            )
        else:
            logger.info(
                'Skipping enrollment code generation for "%s" course. '
                'Because enrollment codes are not allowed for "%s" seat type.',
                course.id,
                ', '.join([getattr(seat.attr, 'certificate_type', '').lower() for seat in course.seat_products]),
            )

    @staticmethod
    def is_course_eligible_for_enrollment_code(course):
        """
        Determine if given course is eligible for an enrollment code.

        Courses that have one of the following seat types are eligible for an enrollment code.
         1. verified
         2. professional
         3. no-id-professional

        Arguments:
            course (Course): E-Commerce course object.

        Returns:
            (bool): True if given course is eligible for enrollment code, False otherwise.
        """
        seat_types = [getattr(seat.attr, 'certificate_type', '').lower() for seat in course.seat_products]
        for seat_type in seat_types:
            if seat_type in ENROLLMENT_CODE_SEAT_TYPES:
                return True
        return False

    @staticmethod
    def get_course_info(course):
        """
        Get course info required for the creation of enrollment code.

        Arguments:
            course (Course): E-Commerce course object.

        Returns:
            (seat_type, price, id_verification_required): A tuple containing the following info
                seat_type: Course seat type e.g. verified, professional or no-id-professional
                price: Price of the course.
                id_verification_required: boolean indicating whether course requires student identity verification.
        Raises:
            (Exception): Raised if given course has either multiple seats eligible for enrollment code or no seat
                eligible for enrollment code.
        """
        seats = [
            seat for seat in course.seat_products if
            getattr(seat.attr, 'certificate_type', '').lower() in ENROLLMENT_CODE_SEAT_TYPES
        ]
        if len(seats) == 1:
            seat = seats[0]
            seat_type = getattr(seat.attr, 'certificate_type', '').lower()
            price = seat.stockrecords.all()[0].price_excl_tax
            id_verification_required = getattr(seat.attr, 'id_verification_required', False)

            return seat_type, price, id_verification_required
        if len(seats) > 1:
            raise CourseInfoError(
                'Course "%s" has multiple seats eligible for enrollment codes.' % course.id
            )

        raise CourseInfoError(
            'Course "%s" does not have any seat eligible for enrollment codes.' % course.id
        )
