import logging

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView

logger = logging.getLogger(__name__)


class ManagementView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'management/index.html'

    def test_func(self):
        return self.request.user.is_superuser

    def post(self, request, *args, **kwargs):  # pylint: disable=unused-argument
        return self.get(request)
