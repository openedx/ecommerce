"""
Django management command to generate a test course for a given course id on LMS
"""
import datetime
import json
import logging

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from oscar.core.loading import get_model
from waffle.models import Flag

from ecommerce.courses.models import Course

Partner = get_model('partner', 'Partner')
logger = logging.getLogger(__name__)


class Command(BaseCommand):

    help = 'Generate courses on ecommerce from a json list of courses. Should only be run in development environments!'

    valid_seat_types = ["audit", "verified", "honor", "professional"]
    default_verified_price = 100
    default_professional_price = 1000
    default_upgrade_deadline = timezone.now() + datetime.timedelta(days=365)

    def add_arguments(self, parser):
        parser.add_argument(
            'courses',
            help='courses to create in JSON format'  # TODO - link test-course JSON format
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            # DEBUG is turned on in development settings and off in production settings
            raise CommandError("Command should only be run in development environments")
        try:
            logger.info("Attempting to create course from the following json object: %s", options["courses"])
            arg = json.loads(options["courses"])
        except ValueError:
            raise CommandError("Invalid JSON object")
        try:
            courses = arg["courses"]
        except KeyError:
            raise CommandError("JSON object is missing courses field")

        partner = Partner.objects.get(short_code='edx')
        site = partner.siteconfiguration.site
        Flag.objects.update_or_create(name='enable_client_side_checkout', defaults={'everyone': True})

        for course_settings in courses:
            if not self._course_is_valid(course_settings):
                logger.warning("Can't create course, proceeding to next course")
                continue

            # Create the course
            org = course_settings["organization"]
            num = course_settings["number"]
            run = course_settings["run"]
            course_name = course_settings["fields"]["display_name"]
            course_id = "course-v1:{org}+{num}+{run}".format(org=org, num=num, run=run)
            defaults = {'name': course_name}
            course, __ = Course.objects.update_or_create(id=course_id, site=site, defaults=defaults)
            logger.info("Created course with id %s", course.id)

            # Create seats
            for seat in course_settings["seats"]:
                self._create_seat(course, seat, partner)

            # Publish the data to the LMS
            course.publish_to_lms()

    def _course_is_valid(self, course):
        """ Returns true if the course is properly formatted and contains acceptable values """
        is_valid = True

        # Check course settings
        missing_settings = []
        if "organization" not in course:
            missing_settings.append("organization")
        if "number" not in course:
            missing_settings.append("number")
        if "run" not in course:
            missing_settings.append("run")
        if "fields" not in course:
            missing_settings.append("fields")
        if "seats" not in course:
            missing_settings.append("seats")
        if missing_settings:
            logger.warning("Course json is missing the following fields: " + str(missing_settings))
            is_valid = False

        # Check fields settings
        if ("fields" in course) and ("display_name" not in course["fields"]):
            logger.warning("Fields json is missing display_name")
            is_valid = False

        # Check seats types
        if "seats" in course:
            for seat in course["seats"]:
                if ("seat_type" not in seat) or (seat["seat_type"] not in self.valid_seat_types):
                    logger.warning("Seat type must be one of " + str(self.valid_seat_types))
                    is_valid = False
                    break

        return is_valid

    def _create_seat(self, course, seat, partner):
        """ Add the specified seat to the course """
        seat_type = seat["seat_type"]
        if seat_type == "audit":
            course.create_or_update_seat("", False, 0, partner)
        elif seat_type == "verified":
            course.create_or_update_seat(
                "verified",
                True,
                self.default_verified_price,
                partner,
                expires=self.default_upgrade_deadline
            )
        elif seat_type == "honor":
            course.create_or_update_seat("honor", False, 0, partner)
        elif seat_type == "professional":
            if "id_verification_required" in seat:
                id_verification_required = seat["id_verification_required"]
            else:
                id_verification_required = True
            course.create_or_update_seat(
                "professional",
                id_verification_required,
                self.default_professional_price,
                partner
            )
        logger.info("Created %s seat for course %s", seat_type, course.id)
