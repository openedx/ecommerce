import logging

import waffle
from django.contrib.auth.decorators import login_required

from django.utils.deprecation import MiddlewareMixin
from edx_django_utils.cache import RequestCache

from edx_rest_framework_extensions.auth.jwt.middleware import USE_JWT_COOKIE_HEADER
from rest_framework.permissions import BasePermission

from ecommerce.extensions.payment.constants import (
    ENABLE_JWT_AUTH_LOGIN_REQUIRED_FLAG_NAME,
    ENABLE_MICROFRONTEND_FOR_BASKET_PAGE_FLAG_NAME,
)

logger = logging.getLogger(__name__)


# TODO: Move to edx-drf-extensions
def jwt_auth_login_required_flag_enabled(request):
    return waffle.flag_is_active(
        request,
        ENABLE_JWT_AUTH_LOGIN_REQUIRED_FLAG_NAME
    )


# TODO: Move to edx-drf-extensions
class JwtAuthLoginRequiredMiddleware(MiddlewareMixin):
    """
    Middleware enables an endpoint with JwtAuthentication to redirect to login for unauthenticated users, rather
    than returning a 401.

    Usage Notes:
    - This middleware must be added before JwtAuthCookieMiddleware.
    - Requires adding LoginRequired permission to endpoint in place of IsAuthenticated.

    """
    _TRIGGER_LOGIN_REDIRECT_CACHE_KEY = 'trigger_login_redirect'

    @classmethod
    def _get_request_cache(cls):
        cache_namespace = 'JwtAuthLoginRequiredMiddleware'
        return RequestCache(cache_namespace).data

    @classmethod
    def _was_login_redirect_triggered(cls):
        return cls._get_request_cache().get(cls._TRIGGER_LOGIN_REDIRECT_CACHE_KEY, False)

    @classmethod
    def trigger_login_redirect(cls):
        """
        Sets a flag to later trigger a redirect to login.

        The LoginRequired permission class uses this to signal that login redirect should occur.

        """
        cls._get_request_cache()[cls._TRIGGER_LOGIN_REDIRECT_CACHE_KEY] = True

    def _includes_base_class(self, iter_classes, base_class):
        """
        Returns whether any class in iter_class is a subclass of the given base_class.
        """
        return any(
            issubclass(current_class, base_class) for current_class in iter_classes,
        )

    def _is_using_login_required_permission_class(self, view_func):
        # Views as functions store the view's class in the 'view_class' attribute.
        # Viewsets store the view's class in the 'cls' attribute.
        view_class = getattr(
            view_func,
            'view_class',
            getattr(view_func, 'cls', view_func),
        )

        view_permission_classes = getattr(view_class, 'permission_classes', tuple())
        return self._includes_base_class(view_permission_classes, LoginRequired)

    def get_login_url(self, request):  # pylint: disable=unused-argument
        """
        Return None for default login url.

        Can be overridden to provide different urls in different circumstances (i.e. A/B testing)

        """
        return None

    def process_view(self, request, view_func, view_args, view_kwargs):  # pylint: disable=unused-argument
        """
        Enables Jwt Authentication for endpoints using the LoginRequired permission class.

        See https://github.com/edx/edx-platform/blob/master/openedx/core/djangoapps/oauth_dispatch/docs/decisions/0009-jwt-in-session-cookie.rst

        """
        if jwt_auth_login_required_flag_enabled(request) and self._is_using_login_required_permission_class(view_func):
            request.META[USE_JWT_COOKIE_HEADER] = 'true'

    def process_response(self, request, response):
        if self._was_login_redirect_triggered():
            fake_decorated_function = lambda request: None
            login_url = self.get_login_url(request)
            return login_required(function=fake_decorated_function, login_url=login_url)(request)

        return response


# TODO: Move to edx-drf-extensions
class LoginRequired(BasePermission):
    """
    DRF permission class that replaces IsAuthenticated if the endpoint should
    redirect to login rather than returning a 401.

    Side-effect:
        Use of this permission declares that JWT Cookies can be used.

    """
    def has_permission(self, request, view):
        if request.user.is_authenticated:
            return True

        JwtAuthLoginRequiredMiddleware.trigger_login_redirect()
        return False


class EcommerceJwtAuthLoginRequiredMiddleware(JwtAuthLoginRequiredMiddleware):
    """
    Overrides JwtAuthLoginRequiredMiddleware to provide a differently login url in
    different circumstances.

    """
    def _use_payment_microfrontend(self, request):
        """
        Return whether the current request should use the payment MFE.
        """
        payment_microfrontend_flag_enabled = waffle.flag_is_active(
            request,
            ENABLE_MICROFRONTEND_FOR_BASKET_PAGE_FLAG_NAME
        )

        return (
            request.site.siteconfiguration.enable_microfrontend_for_basket_page and
            request.site.siteconfiguration.payment_microfrontend_url and
            payment_microfrontend_flag_enabled
        )

    def get_login_url(self, request):
        """
        When using the payment mfe, use lms login to get jwt cookies.
        Otherwise, return None to get the default login for the social-auth SSO flow.
        """
        if jwt_auth_login_required_flag_enabled(request) and self._use_payment_microfrontend(request):
            return request.site.siteconfiguration.build_lms_url('/login')

        return None

