""" This command populate organization in existing courses."""
from __future__ import unicode_literals

from django.core.management import BaseCommand
from opaque_keys.edx.keys import CourseKey

from ecommerce.courses.models import Course


class Command(BaseCommand):
    """Populate organization in courses."""

    help = 'Populate organization in courses'

    def handle(self, *args, **options):
        for course in Course.objects.all().iterator():
            course.organization = CourseKey.from_string(course.id).org
            course.save(update_fields=['organization'])
