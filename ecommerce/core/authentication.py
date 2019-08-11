import logging

import waffle
from edx_rest_framework_extensions.auth.jwt.middleware import JwtAuthWithLoginRequiredMiddleware


from ecommerce.extensions.payment.constants import (
    ENABLE_JWT_AUTH_WITH_LOGIN_REQUIRED_FLAG_NAME,
    ENABLE_MICROFRONTEND_FOR_BASKET_PAGE_FLAG_NAME,
    ENABLE_LMS_LOGIN_FOR_LOGIN_REQUIRED_FLAG_NAME,
)

logger = logging.getLogger(__name__)


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
