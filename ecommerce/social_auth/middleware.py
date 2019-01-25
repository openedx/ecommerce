"""Middleware classes for social_auth."""

import logging

from django.shortcuts import redirect
from django.urls import reverse
from social_core.exceptions import AuthStateMissing
from social_django.middleware import SocialAuthExceptionMiddleware

log = logging.getLogger(__name__)


class ExceptionMiddleware(SocialAuthExceptionMiddleware):
    """Custom middleware that handles conditional redirection."""

    def process_exception(self, request, exception):
        """Handles specific exception raised by Python Social Auth eg AuthStateMissing."""

        request_path = request.path
        if request_path and isinstance(exception, AuthStateMissing):
            if request_path == reverse('social:complete', args=['edx-oidc']):

                from django.conf import settings
                redirect_url = settings.SOCIAL_AUTH_EDX_OIDC_LOGOUT_URL
                exception_logs = 'AuthStateMissing exception'

                redirect_url = redirect_url if redirect_url else '/'
                if redirect_url != '/':
                    exception_logs += ', redirecting learner to lms logout url.'
                else:
                    exception_logs += ', redirecting learner to ecommerce index page.'

                log.info(exception_logs)
                return redirect(redirect_url)

        return super(ExceptionMiddleware, self).process_exception(request, exception)
