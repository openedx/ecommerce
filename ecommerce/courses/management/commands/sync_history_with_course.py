from __future__ import unicode_literals

import logging

from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand
from django.db import transaction

from ecommerce.courses.models import Course


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sync course history data with course created modified date.'

    def handle(self, *args, **options):
        courses = Course.objects.all()

        with transaction.atomic():
            for course in courses:
                try:
                    course.created = course.history.earliest().history_date
                    course.modified = course.history.latest().history_date
                    course.save()
                except ObjectDoesNotExist:
                    logger.warning(
                        'History object for course with course_id: %s does not exist',
                        course.id
                    )
                    course.created = None
                    course.modified = None
                    course.save()
