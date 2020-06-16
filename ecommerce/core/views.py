"""HTTP endpoint for verifying the health of the ecommerce front-end."""


import logging
import uuid

from auth_backends.views import EdxOAuth2LogoutView
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login
from django.contrib.auth.decorators import login_required
from django.db import DatabaseError, connection, transaction
from django.http import Http404, JsonResponse
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.generic import View

from ecommerce.core.constants import Status

try:
    import newrelic.agent
except ImportError:  # pragma: no cover
    newrelic = None  # pylint: disable=invalid-name

logger = logging.getLogger(__name__)
User = get_user_model()


@transaction.non_atomic_requests
def health(_):
    """Allows a load balancer to verify that the ecommerce front-end service is up.

    Checks the status of the database connection.

    Returns:
        HttpResponse: 200 if the ecommerce front-end is available, with JSON data
            indicating the health of each required service
        HttpResponse: 503 if the ecommerce front-end is unavailable, with JSON data
            indicating the health of each required service

    Example:
        >>> response = requests.get('https://ecommerce.edx.org/health')
        >>> response.status_code
        200
        >>> response.content
        '{"overall_status": "OK", "detailed_status": {"database_status": "OK"}}'
    """
    if newrelic:  # pragma: no cover
        newrelic.agent.ignore_transaction()

    overall_status = database_status = Status.UNAVAILABLE

    try:
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        database_status = Status.OK
    except DatabaseError:
        database_status = Status.UNAVAILABLE

    overall_status = Status.OK if (database_status == Status.OK) else Status.UNAVAILABLE

    data = {
        'overall_status': overall_status,
        'detailed_status': {
            'database_status': database_status,
        },
    }

    if overall_status == Status.OK:
        return JsonResponse(data)

    return JsonResponse(data, status=503)


class AutoAuth(View):
    """Creates and authenticates a new User with superuser permissions.

    If the ENABLE_AUTO_AUTH setting is not True, returns a 404.
    """
    lms_user_id = 45654

    def get(self, request):
        if not getattr(settings, 'ENABLE_AUTO_AUTH', None):
            raise Http404

        username_prefix = getattr(settings, 'AUTO_AUTH_USERNAME_PREFIX', 'auto_auth_')

        # Create a new user with staff permissions
        username = password = username_prefix + uuid.uuid4().hex[0:20]
        User.objects.create_superuser(username, email=None, password=password, lms_user_id=self.lms_user_id)

        # Log in the new user
        user = authenticate(username=username, password=password)
        login(request, user)

        return redirect('/')


class StaffOnlyMixin:
    """ Makes sure only staff users can access the view. """

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_staff:
            raise Http404

        return super(StaffOnlyMixin, self).dispatch(request, *args, **kwargs)


class LogoutView(EdxOAuth2LogoutView):
    """ Logout view that redirects the user to the LMS logout page. """

    def get_redirect_url(self, *args, **kwargs):
        return self.request.site.siteconfiguration.oauth_settings['SOCIAL_AUTH_EDX_OAUTH2_LOGOUT_URL']
