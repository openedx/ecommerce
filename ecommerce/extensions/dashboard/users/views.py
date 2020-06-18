

import logging

import requests
import waffle
from django.conf import settings
from django.contrib import messages
from django.utils.translation import ugettext_lazy as _
from oscar.apps.dashboard.users.views import UserDetailView as CoreUserDetailView

from ecommerce.core.url_utils import get_lms_enrollment_api_url

logger = logging.getLogger(__name__)


class UserDetailView(CoreUserDetailView):
    def get_context_data(self, **kwargs):
        context = super(UserDetailView, self).get_context_data(**kwargs)

        if waffle.switch_is_active('user_enrollments_on_dashboard'):
            context['enrollments'] = self._get_enrollments()

        return context

    def _get_enrollments(self):
        """Retrieve the enrollments for the User being viewed."""
        username = self.object.username
        try:
            url = '{}?user={}'.format(get_lms_enrollment_api_url(), username)
            timeout = settings.ENROLLMENT_FULFILLMENT_TIMEOUT

            headers = {
                'Content-Type': 'application/json',
                'X-Edx-Api-Key': settings.EDX_API_KEY
            }

            response = requests.get(url, headers=headers, timeout=timeout)

            status_code = response.status_code
            if status_code == 200:
                return response.json()
            logger.warning(u'Failed to retrieve enrollments for [%s]. Enrollment API returned status code [%d].',
                           username, status_code)
        except Exception:  # pylint: disable=broad-except
            logger.exception(u'An unexpected error occurred while retrieving enrollments for [%s].', username)

        messages.add_message(self.request, messages.ERROR, _(u'Failed to retrieve enrollment data.'))
        return []
