"""
Django rules for Refund
"""


import rules
from edx_rbac.utils import user_has_access_via_database

from ecommerce.core.constants import ORDER_MANAGER_ROLE
from ecommerce.core.models import EcommerceFeatureRoleAssignment


@rules.predicate
def request_user_has_refund_access(user):
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


rules.add_perm('refund.add_refund', request_user_has_refund_access)
rules.add_perm('refund.change_refund', request_user_has_refund_access)
rules.add_perm('refund.delete_refund', request_user_has_refund_access)
rules.add_perm('refund.add_refundline', request_user_has_refund_access)
rules.add_perm('refund.change_refundline', request_user_has_refund_access)
rules.add_perm('refund.delete_refundline', request_user_has_refund_access)
rules.add_perm('refund', rules.always_allow)
