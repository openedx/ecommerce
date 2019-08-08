import logging

from django.shortcuts import redirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin
from django.utils.http import urlquote_plus
from edx_django_utils.cache import RequestCache
from edx_rest_framework_extensions.auth.jwt.middleware import USE_JWT_COOKIE_HEADER
from rest_framework.permissions import BasePermission

logger = logging.getLogger(__name__)


def _login_redirect_to_lms(request):
    """
    This view redirects to the LMS login view. It is used for Django's LOGIN_URL
    setting, which is where unauthenticated requests to protected endpoints are redirected.
    """
    # TODO: Why isn't the next_url appearing?
    next_url = request.GET.get('next')
    absolute_next_url = request.build_absolute_uri(next_url)
    login_url = '/login{params}'.format(
        params='?next=' + urlquote_plus(absolute_next_url) if next_url else '',
    )
    lms_login_url = 'http://localhost:18000' + login_url
    # TODO: Is this what it should be? It is going to: http://edx.devstack.lms:18000/login?...
    # lms_login_url = request.site.siteconfiguration.build_lms_url(login_url)
    return redirect(lms_login_url)


class UseJwtCookieMiddleware(MiddlewareMixin):
    """
    Enables use of Jwt Cookies when working with microfrontends.

    For example, /basket/add is called before reaching the payment microfrontend (mfe), and we do not want to use
    the social-auth SSO flow (which is slow), before getting to the payment mfe which will then use Jwt Authentication.

    Notes:
    - This middleware must be added before JwtAuthCookieMiddleware.
    - Requires IsAuthenticatedOrLoginRequired permission to work correctly

    """
    _CACHE_NAMESPACE = 'UseJwtCookieMiddleware'
    _REDIRECT_ON_FAILURE_CACHE_KEY = 'redirect_on_failure'

    @classmethod
    def _cache(cls):
        return RequestCache(cls._CACHE_NAMESPACE).data

    @classmethod
    def _get_redirect_on_permission_failure(cls):
        return cls._cache().get(cls._REDIRECT_ON_FAILURE_CACHE_KEY, False)

    @classmethod
    def set_redirect_on_permission_failure(cls):
        """
        Enables coordination with IsAuthenticatedOrLoginRequired permission class to signal when
        to redirect for permission failures.
        """
        cls._cache()[cls._REDIRECT_ON_FAILURE_CACHE_KEY] = True

    def process_request(self, request):
        # TODO: Maybe flag is needed, because this call currently requires a user, and we don't have one yet.
        # Problem:
        # - Can't import use_payment_microfrontend.  Don't want to move it in here yet, because I think there are
        #   issues with that.
        #if use_payment_microfrontend(request):
        if True:
            request.META[USE_JWT_COOKIE_HEADER] = 'true'

    def process_response(self, request, response):
        if self._get_redirect_on_permission_failure():
            # TODO: Need to fix this condition.  See above.
            #if use_payment_microfrontend(request):
            if True:
                return _login_redirect_to_lms(request)
            else:
                return reverse('login')

        return response


class IsAuthenticatedOrLoginRequired(BasePermission):
    def has_permission(self, request, view):
        if request.user.is_authenticated:
            return True

        # Tell the UseJwtCookieMiddleware to redirect to login
        UseJwtCookieMiddleware.set_redirect_on_permission_failure()
        return False
