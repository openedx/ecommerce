import logging

import waffle
from django.contrib.auth.decorators import login_required

from django.utils.deprecation import MiddlewareMixin
from edx_django_utils.cache import RequestCache

from edx_rest_framework_extensions.auth.jwt.middleware import USE_JWT_COOKIE_HEADER
from rest_framework.permissions import IsAuthenticated

from ecommerce.extensions.payment.constants import (
    ENABLE_JWT_AUTH_WITH_LOGIN_REQUIRED_FLAG_NAME,
    ENABLE_MICROFRONTEND_FOR_BASKET_PAGE_FLAG_NAME,
    ENABLE_LMS_LOGIN_FOR_LOGIN_REQUIRED_FLAG_NAME,
)

logger = logging.getLogger(__name__)


# TODO: Move to edx-drf-extensions
class JwtAuthWithLoginRequiredMiddleware(MiddlewareMixin):
    """
    Middleware enables DRF JwtAuthentication authentication class for endpoints
    using the LoginRequired permission class.

    Enables a non-standard use of DRF, because DRF only supports returning
    a 401 for unauthorized users, but this middleware allows a DRF endpoint
    to redirect to login.

    This can be used to convert a plan Django view using @login_required into a
    DRF APIView, which is useful to enable our DRF JwtAuthentication class.

    Usage Notes:
    - This middleware must be added before JwtAuthCookieMiddleware.
    - Only affects endpoints using the LoginRequired permission class.

    See https://github.com/edx/edx-platform/blob/master/openedx/core/djangoapps/oauth_dispatch/docs/decisions/0009-jwt-in-session-cookie.rst
    """
    _LOGIN_REQUIRED_FOUND_CACHE_KEY = 'login_required_found'

    def _get_request_cache(cls):
        cache_namespace = 'JwtAuthWithLoginRequiredMiddleware'
        return RequestCache(cache_namespace).data

    def _includes_base_class(self, iter_classes, base_class):
        """
        Returns whether any class in iter_class is a subclass of the given base_class.
        """
        return any(
            issubclass(current_class, base_class) for current_class in iter_classes,
        )

    def _is_login_required_found(self):
        """
        Returns True if LoginRequired permission was found, and False otherwise.
        """
        return self._get_request_cache().get(self._LOGIN_REQUIRED_FOUND_CACHE_KEY, False)

    def _check_and_cache_login_required_found(self, view_func):
        """
        Checks for LoginRequired permission and caches the result.
        """
        # Views as functions store the view's class in the 'view_class' attribute.
        # Viewsets store the view's class in the 'cls' attribute.
        view_class = getattr(
            view_func,
            'view_class',
            getattr(view_func, 'cls', view_func),
        )

        view_permission_classes = getattr(view_class, 'permission_classes', tuple())
        is_login_required_found = self._includes_base_class(view_permission_classes, LoginRequired)
        self._get_request_cache()[self._LOGIN_REQUIRED_FOUND_CACHE_KEY] = is_login_required_found

    def get_login_url(self, request):  # pylint: disable=unused-argument
        """
        Return None for default login url.

        Can be overridden for slow-rollout or A/B testing of transition to other login mechanisms.
        """
        return None

    def is_jwt_auth_enabled_with_login_required(self, request, view_func):  # pylint: disable=unused-argument
        """
        Returns True if JwtAuthentication is enabled with the LoginRequired permission class.

        Can be overridden for slow roll-out or A/B testing.
        """
        return self._is_login_required_found()

    def process_view(self, request, view_func, view_args, view_kwargs):  # pylint: disable=unused-argument
        """
        Enables Jwt Authentication for endpoints using the LoginRequired permission class.
        """
        self._check_and_cache_login_required_found(view_func)
        if self.is_jwt_auth_enabled_with_login_required(request, view_func):
            request.META[USE_JWT_COOKIE_HEADER] = 'true'

    def process_response(self, request, response):
        """
        Redirects unauthenticated users to login when LoginRequired permission class was used.
        """
        if self._is_login_required_found() and not request.user.is_authenticated:
            fake_decorated_function = lambda request: None
            login_url = self.get_login_url(request)
            return login_required(function=fake_decorated_function, login_url=login_url)(request)

        return response


# TODO: Move to edx-drf-extensions
class LoginRequired(IsAuthenticated):
    """
    A non-standard DRF permission class that will login redirect unauthorized users.

    It can be used to convert a plan Django view using @login_required into a
    DRF APIView, which is useful to enable our DRF JwtAuthentication class.

    This permission is non-standard because DRF only supports returning a 401
    status for unauthorized users.

    Requires JwtAuthWithLoginRequiredMiddleware in order to work.

    """
    pass


class EcommerceJwtAuthWithLoginRequiredMiddleware(JwtAuthWithLoginRequiredMiddleware):
    """
    Overrides JwtAuthWithLoginRequiredMiddleware to provide a different login url in
    different circumstances.

    """
    def _jwt_auth_login_required_flag_enabled(self, request):
        return waffle.flag_is_active(
            request,
            ENABLE_JWT_AUTH_WITH_LOGIN_REQUIRED_FLAG_NAME
        )

    def _lms_login_for_login_required_flag_enabled(self, request):
        return waffle.flag_is_active(
            request,
            ENABLE_LMS_LOGIN_FOR_LOGIN_REQUIRED_FLAG_NAME
        )

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

    def is_jwt_auth_enabled_with_login_required(self, request, view_func):
        if self._jwt_auth_login_required_flag_enabled(request):
            return super(
                EcommerceJwtAuthWithLoginRequiredMiddleware, self
            ).is_jwt_auth_enabled_with_login_required(request, view_func)

        return False

    def get_login_url(self, request):
        """
        When using the payment mfe, use lms login to get jwt cookies.
        Otherwise, return None to get the default login for the social-auth SSO flow.
        """
        if self._lms_login_for_login_required_flag_enabled(request) and self._use_payment_microfrontend(request):
            return request.site.siteconfiguration.build_lms_url('/login')

        return None
