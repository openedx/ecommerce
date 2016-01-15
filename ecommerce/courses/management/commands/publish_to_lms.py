""" This command publish the courses to LMS."""

import logging
from optparse import make_option
import os

from django.core.management import BaseCommand, CommandError
from ecommerce.courses.models import Course

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Publish the courses to LMS."""

    help = 'Publish the courses to LMS'
    option_list = BaseCommand.option_list + (
        make_option(
            '--course_ids_file',
            action='store',
            dest='course_ids_file',
            default=None,
            help='Path to file to read courses from.'
        ),
    )

    def handle(self, *args, **options):
        errors_dict = {}
        course_ids_file = options['course_ids_file']
        if not course_ids_file or not os.path.exists(course_ids_file):
            raise CommandError("Pass the correct absolute path to course ids file as --course_ids_file argument.")

        with open(course_ids_file, 'r') as course_ids:
            self.stderr.write("Publishing courses to LMS")
            for course_id in course_ids:
                try:
                    course_id = course_id.strip()
                    course = Course.objects.get(id=course_id)
                    publishing_error = course.publish_to_lms()
                    if publishing_error:
                        errors_dict[course_id] = publishing_error
                except Course.DoesNotExist:
                    errors_dict[course_id] = "The course {course_id} does not exists.".format(course_id=course_id)
        if errors_dict:
            error_str = ["Course_id={} Error={}".format(course_id, error_msg) for course_id, error_msg
                         in errors_dict.items()]
            error_str = "\n".join(["Following Courses failed while publishing through management command:"] + error_str)
            self.stderr.write(error_str)
            logger.error(error_str)
        else:
            self.stderr.write("All Courses published successfully.")
            logger.info("All Courses published successfully.")
        self.stderr.write("Done.")
        logger.info("Done.")
