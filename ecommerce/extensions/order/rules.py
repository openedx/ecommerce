"""
Django rules for Refund
"""

import crum
import rules
from edx_rbac.utils import request_user_has_implicit_access_via_jwt, user_has_access_via_database
# pylint: disable=no-name-in-module
from edx_rest_framework_extensions.auth.jwt.authentication import get_decoded_jwt_from_auth
from edx_rest_framework_extensions.auth.jwt.cookies import get_decoded_jwt

from ecommerce.core.constants import ORDER_MANAGER_ROLE
from ecommerce.core.models import EcommerceFeatureRoleAssignment


@rules.predicate
def request_user_has_implicit_access(user):  # pylint: disable=unused-argument
    """
    Check that if request user has implicit access to `ORDER_MANAGER_ROLE` feature role.
     Returns:
        boolean: whether the request user has access or not
    """
    request = crum.get_current_request()
    decoded_jwt = get_decoded_jwt(request) or get_decoded_jwt_from_auth(request)

    return request_user_has_implicit_access_via_jwt(decoded_jwt, ORDER_MANAGER_ROLE)


@rules.predicate
def request_user_has_explicit_access(user):
    """
    Check that if request user has explicit access to `ORDER_MANAGER_ROLE` feature role.
    Returns:
        boolean: whether the request user has access or not
    """
    if user.is_authenticated:
        return user_has_access_via_database(
            user,
            ORDER_MANAGER_ROLE,
            EcommerceFeatureRoleAssignment
        )

    return False


rules.add_perm(
    'order.add_markordersstatuscompleteconfig',
    request_user_has_implicit_access | request_user_has_explicit_access
)
rules.add_perm(
    'order.change_markordersstatuscompleteconfig',
    request_user_has_implicit_access | request_user_has_explicit_access
)
rules.add_perm(
    'order.delete_markordersstatuscompleteconfig',
    request_user_has_implicit_access | request_user_has_explicit_access
)
rules.add_perm('order', rules.always_allow)
