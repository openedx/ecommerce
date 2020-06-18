"""
Django rules for enterprise
"""


import crum
import rules
from edx_rbac.utils import request_user_has_implicit_access_via_jwt, user_has_access_via_database
# pylint: disable=no-name-in-module
from edx_rest_framework_extensions.auth.jwt.authentication import get_decoded_jwt_from_auth
from edx_rest_framework_extensions.auth.jwt.cookies import get_decoded_jwt

from ecommerce.core.constants import ENTERPRISE_COUPON_ADMIN_ROLE
from ecommerce.core.models import EcommerceFeatureRoleAssignment


@rules.predicate
def request_user_has_implicit_access(user, context):  # pylint: disable=unused-argument
    """
    Check that if request user has implicit access to `ENTERPRISE_COUPON_ADMIN_ROLE` feature role.
     Returns:
        boolean: whether the request user has access or not
    """
    request = crum.get_current_request()
    decoded_jwt = get_decoded_jwt(request) or get_decoded_jwt_from_auth(request)
    if not context:
        return False
    return request_user_has_implicit_access_via_jwt(decoded_jwt, ENTERPRISE_COUPON_ADMIN_ROLE, context)


@rules.predicate
def request_user_has_explicit_access(user, context):
    """
    Check that if request user has explicit access to `ENTERPRISE_COUPON_ADMIN_ROLE` feature role.
    Returns:
        boolean: whether the request user has access or not
    """
    if not context:
        return False
    return user_has_access_via_database(
        user,
        ENTERPRISE_COUPON_ADMIN_ROLE,
        EcommerceFeatureRoleAssignment,
        context=context
    )


rules.add_perm(
    'enterprise.can_view_coupon',
    request_user_has_implicit_access |
    request_user_has_explicit_access
)
rules.add_perm(
    'enterprise.can_assign_coupon',
    request_user_has_implicit_access |
    request_user_has_explicit_access
)
