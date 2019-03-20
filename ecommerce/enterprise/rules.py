"""
Django rules for enterprise
"""
from __future__ import absolute_import

import rules
from edx_rbac.utils import user_has_access_via_database

from ecommerce.core.constants import ENTERPRISE_COUPON_ADMIN_ROLE
from ecommerce.core.models import EcommerceFeatureRoleAssignment


@rules.predicate
def is_enterprise_coupon_admin(user, obj):  # pylint: disable=unused-argument
    """
    Returns whether the user is an enterprise admin.
    """
    role_name = ENTERPRISE_COUPON_ADMIN_ROLE
    role_assignment_class = EcommerceFeatureRoleAssignment
    return user_has_access_via_database(user, role_name, role_assignment_class)


rules.add_perm('enterprise.can_view_coupon', is_enterprise_coupon_admin)
rules.add_perm('enterprise.can_assign_coupon', is_enterprise_coupon_admin)
