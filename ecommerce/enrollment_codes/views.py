from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView

class StaffOnlyMixin(object):
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_staff:
            raise Http404

        return super(StaffOnlyMixin, self).dispatch(request, *args, **kwargs)


class EnrollmentCodeAppView(StaffOnlyMixin, TemplateView):
    template_name = 'enrollment_codes/enrollment_code_app.html'
