import datetime

from django.core.management import call_command
from testfixtures import LogCapture

from ecommerce.courses.models import Course
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.tests.testcases import TestCase

LOGGER_NAME = 'ecommerce.courses.management.commands.sync_history_with_course'


class SyncHistoryTests(TestCase):
    def setUp(self):
        super(SyncHistoryTests, self).setUp()
        self.course = CourseFactory(id='edx/Demo_Course/DemoX', site=self.site)

    def test_history_not_exist(self):
        self.course.history.all().delete()
        with LogCapture(LOGGER_NAME) as log:
            call_command('sync_history_with_course')
            log.check(
                (
                    LOGGER_NAME,
                    'WARNING',
                    'History object for course with course_id: edx/Demo_Course/DemoX does not exist'
                )
            )

    def test_sync_history_data(self):
        self.course.created = self.course.created + datetime.timedelta(days=1)
        self.course.modified = self.course.created + datetime.timedelta(days=1)
        self.course.save()
        latest_history_update = self.course.history.latest().history_date
        call_command('sync_history_with_course')
        course = Course.objects.get(id='edx/Demo_Course/DemoX')
        self.assertEqual(course.created, self.course.history.earliest().history_date)
        self.assertEqual(course.modified, latest_history_update)
