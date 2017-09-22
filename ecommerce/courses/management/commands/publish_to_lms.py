""" This command publish the courses to LMS."""
from __future__ import unicode_literals

import logging
import os

from django.core.management import BaseCommand, CommandError

from ecommerce.courses.models import Course

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Publish the courses to LMS."""

    help = 'Publish the courses to LMS'

    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    logger.addHandler(ch)

    def add_arguments(self, parser):
        parser.add_argument('--course_ids_file',
                            action='store',
                            dest='course_ids_file',
                            default=None,
                            help='Path to file to read courses from.')

    def handle(self, *args, **options):
        failed = 0
        course_ids_file = options['course_ids_file']
        if not course_ids_file or not os.path.exists(course_ids_file):
            raise CommandError("Pass the correct absolute path to course ids file as --course_ids_file argument.")

        with open(course_ids_file, 'r') as file_handler:
            course_ids = file_handler.readlines()
            total_courses = len(course_ids)
            logger.info("Publishing %d courses.", total_courses)
            for index, course_id in enumerate(course_ids, start=1):
                try:
                    course_id = course_id.strip()
                    course = Course.objects.get(id=course_id)
                    publishing_error = course.publish_to_lms()
                    if publishing_error:
                        failed += 1
                        logger.error(
                            u"(%d/%d) Failed to publish %s: %s", index, total_courses, course_id, publishing_error
                        )
                    else:
                        logger.info(u"(%d/%d) Successfully published %s.", index, total_courses, course_id)
                except Course.DoesNotExist:
                    failed += 1
                    logger.error(
                        u"(%d/%d) Failed to publish %s: Course does not exist.", index, total_courses, course_id
                    )
        if failed:
            logger.error("Completed publishing courses. %d of %d failed.", failed, total_courses)
        else:
            logger.info("All %d courses successfully published.", total_courses)
