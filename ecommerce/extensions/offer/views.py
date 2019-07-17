from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView

from ecommerce.courses.models import Course


class EmailConfirmationRequiredView(TemplateView):
    template_name = 'edx/email_confirmation_required.html'

    def get_context_data(self, **kwargs):
        context = super(EmailConfirmationRequiredView, self).get_context_data(**kwargs)

        course = self._get_course()
        context.update({
            'course_name': course and course.name,
            'user_email': self.request.user and self.request.user.email,
        })

        return context

    def _get_course(self):
        course_id = self.request.GET.get('course_id')
        if course_id:
            return get_object_or_404(Course, id=course_id)
        return None
