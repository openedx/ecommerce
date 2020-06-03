import logging

from django.http import Http404
from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from requests.exceptions import ConnectionError as ReqConnectionError
from requests.exceptions import Timeout
from slumber.exceptions import SlumberHttpBaseException

from ecommerce.courses.models import Course
from ecommerce.courses.utils import get_course_detail

logger = logging.getLogger(__name__)


class EmailConfirmationRequiredView(TemplateView):
    template_name = 'edx/email_confirmation_required.html'

    def get_context_data(self, **kwargs):
        context = super(EmailConfirmationRequiredView, self).get_context_data(**kwargs)

        courses = self._get_courses()
        context.update({
            'courses': courses,
            'user_email': self.request.user and self.request.user.email,
        })

        return context

    def _get_courses(self):
        course_keys = []
        course_ids = self.request.GET.getlist('course_id')
        for course_id in course_ids:
            try:
                course_run_key = CourseKey.from_string(course_id)
            except InvalidKeyError:
                # An `InvalidKeyError` is thrown because this course key not a course run key
                # We will get the title from the discovery.
                try:
                    course = get_course_detail(self.request.site, course_id)
                    course_keys.append(course.get('title'))
                except (ReqConnectionError, SlumberHttpBaseException, Timeout) as exc:
                    logger.exception(
                        '[Account activation failure] User tried to excess the course from discovery and failed.'
                        'User: %s, course: %s, Message: %s',
                        self.request.user.id,
                        course_id,
                        exc
                    )
                    raise Http404
            else:
                course_run = get_object_or_404(Course, id=course_run_key)
                course_keys.append(course_run.name)
        return course_keys
