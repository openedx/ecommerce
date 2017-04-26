from __future__ import unicode_literals

from django.views.generic import TemplateView

from ecommerce.core.views import StaffOnlyMixin

class ProgramAppView(StaffOnlyMixin, TemplateView):
    template_name = 'programs/program_app.html'

    def get_context_data(self, **kwargs):
        context = super(ProgramAppView, self).get_context_data(**kwargs)
        context['admin'] = 'program'
        return context
