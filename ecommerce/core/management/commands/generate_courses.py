"""
Django management command to generate a test course from a course config json
"""


import datetime
import json
import logging

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from oscar.core.loading import get_model
from waffle.models import Flag

from ecommerce.courses.models import Course

Partner = get_model('partner', 'Partner')
logger = logging.getLogger(__name__)


class Command(BaseCommand):

    help = 'Generate courses on ecommerce from a json list of courses.'

    course_enrollment_settings = [
        "audit",
        "verified",
        "honor",
        "professional_education",
        "no_id_verification",
        "credit",
        "credit_provider"
    ]
    default_upgrade_deadline = timezone.now() + datetime.timedelta(days=365)

    def add_arguments(self, parser):
        parser.add_argument(
            'courses_json',
            help='courses to create in JSON format'  # TODO - link test-course JSON format
        )

    def handle(self, *args, **options):
        try:
            courses = json.loads(options["courses_json"])["courses"]
        except ValueError:
            raise CommandError("Invalid JSON object")
        except KeyError:
            raise CommandError("JSON object is missing courses list")

        Flag.objects.update_or_create(name='enable_client_side_checkout', defaults={'everyone': True})
        for course_settings in courses:
            if not self._course_is_valid(course_settings):
                logger.warning("Can't create course, proceeding to next course")

                continue

            partner_code = course_settings["partner"]
            try:
                partner = Partner.objects.get(short_code=partner_code)
            except Partner.DoesNotExist:
                logger.warning(
                    "%s partner does not exist. Can't create course, proceeding to next course.",
                    partner_code
                )
                continue

            # Create the course
            org = course_settings["organization"]
            num = course_settings["number"]
            run = course_settings["run"]
            course_name = course_settings["fields"]["display_name"]
            course_id = "course-v1:{org}+{num}+{run}".format(org=org, num=num, run=run)
            defaults = {'name': course_name}
            course, __ = Course.objects.update_or_create(id=course_id, partner=partner, defaults=defaults)
            logger.info("Created course with id %s", course.id)

            # Create seats
            enrollment = course_settings["enrollment"]
            self._create_seats(enrollment, course)

            # Publish the data to the LMS
            if course.publish_to_lms():
                logger.warning('An error occurred while attempting to publish [%s] to LMS', course_id)
            else:
                logger.info('Published course modes for [%s] to LMS', course_id)

    def _course_is_valid(self, course):
        """ Returns true if the course is properly formatted and contains acceptable values """
        is_valid = True

        # Check course settings
        required_course_settings = [
            "organization",
            "number",
            "run",
            "partner",
            "fields",
            "enrollment",
        ]
        for setting in required_course_settings:
            if setting not in course:
                logger.warning("Course json is missing %s", setting)
                is_valid = False

        # Check fields settings
        required_field_settings = [
            "display_name"
        ]
        if "fields" in course:
            for setting in required_field_settings:
                if setting not in course["fields"]:
                    logger.warning("Fields json is missing %s", setting)
                    is_valid = False

        # Check enrollment settings
        required_enrollment_settings = self.course_enrollment_settings
        if "enrollment" in course:
            for setting in required_enrollment_settings:
                if setting not in course["enrollment"]:
                    logger.warning("Enrollment json is missing %s", setting)
                    is_valid = False

        return is_valid

    def _create_seats(self, enrollment, course):
        """ Create the seats for a given course based on the enrollment parameters """
        for setting in enrollment:
            if setting not in self.course_enrollment_settings:
                logger.info("%s is not a recognized enrollment setting", setting)
            else:
                logger.info("%s has been set to %s", setting, enrollment[setting])

        if enrollment["audit"]:
            course.create_or_update_seat("", False, 0)
            logger.info("Created audit seat for course %s", course.id)
        if enrollment["honor"]:
            course.create_or_update_seat("honor", False, 0)
            logger.info("Created honor seat for course %s", course.id)
        if enrollment["verified"]:
            course.create_or_update_seat(
                certificate_type="verified",
                id_verification_required=True,
                price=100,
                expires=self.default_upgrade_deadline
            )
            logger.info("Created verified seat for course %s", course.id)
        if enrollment["professional_education"]:
            id_verification_required = not enrollment["no_id_verification"]
            course.create_or_update_seat(
                certificate_type="professional",
                id_verification_required=id_verification_required,
                price=1000
            )
            logger.info(
                "Created professional seat for course %s. ID verification requirement has been set to %s",
                course.id,
                id_verification_required
            )
        if enrollment["credit"]:
            credit_provider = enrollment["credit_provider"]
            course.create_or_update_seat(
                certificate_type="credit",
                id_verification_required=True,
                price=2000,
                credit_provider=credit_provider,
                credit_hours=100
            )
            logger.info(
                "Created credit seat for course %s, with credit provider %s",
                course.id,
                credit_provider
            )
