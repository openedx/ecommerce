"""
Django rules for enterprise
"""
from __future__ import absolute_import

import rules
import waffle
from edx_rbac.utils import get_decoded_jwt_from_request, get_request_or_stub, request_user_has_implicit_access_via_jwt
from oscar.core.loading import get_model

from ecommerce.core.constants import ENTERPRISE_COUPON_ADMIN_ROLE, SYSTEM_ENTERPRISE_ADMIN_ROLE
from ecommerce.core.models import EcommerceFeatureRoleAssignment
from ecommerce.enterprise.constants import USE_ROLE_BASED_ACCESS_CONTROL
from ecommerce.invoice.models import Invoice

Basket = get_model('basket', 'Basket')
Order = get_model('order', 'Order')
Line = get_model('basket', 'Line')
Product = get_model('catalogue', 'Product')


def has_correct_context_for_implicit_access(obj, decoded_jwt, system_wide_role_name):
    """
    Check if request has correct role assignment context.
    """
    jwt_roles_claim = decoded_jwt.get('roles', []) if decoded_jwt else []
    print(jwt_roles_claim)
    for role_data in jwt_roles_claim:
        print(role_data)
        role_in_jwt, enterprise_id_in_jwt = role_data.split(':')
        if role_in_jwt == system_wide_role_name:
            if isinstance(obj, unicode):
                enterprise_id_in_request = obj
                print("path number 1")
                print(enterprise_id_in_jwt)
                print(enterprise_id_in_request)
                return enterprise_id_in_jwt == enterprise_id_in_request
            elif isinstance(obj, Product):
                invoices = Invoice.objects.filter(
                    business_client__enterprise_customer_uuid=enterprise_id_in_jwt
                )
                orders = Order.objects.filter(id__in=[invoice.order_id for invoice in invoices])
                basket_lines = Line.objects.filter(
                    basket_id__in=[order.basket_id for order in orders],
                    product=obj,
                )
                if basket_lines.exists():
                    return True
    return False


def has_correct_context_for_explicit_access(user, obj):
    """
    Check if request has correct role assignment context.
    """
    if isinstance(obj, unicode):
        enterprise_id = obj
    elif isinstance(obj, Product):
        basket = Basket.objects.filter(lines__product_id=obj.id).first()
        invoice = Invoice.objects.get(order__basket=basket)
        enterprise_id = str(invoice.business_client.enterprise_customer_uuid)
    else:
        return False
    try:
        role_assignment = EcommerceFeatureRoleAssignment.objects.get(
            user=user,
            role__name=ENTERPRISE_COUPON_ADMIN_ROLE,
            enterprise_id=enterprise_id
        )
    except EcommerceFeatureRoleAssignment.DoesNotExist:
        return False

    # if there is no enterprise_id set than user is allowed
    if role_assignment.get_context() is None:
        return True
    return role_assignment.get_context()


@rules.predicate
def request_user_has_implicit_access(user, obj):  # pylint: disable=unused-argument
    """
    Check that if request user has implicit access to `ENTERPRISE_COUPON_ADMIN_ROLE` feature role.
     Returns:
        boolean: whether the request user has access or not
    """
    if not waffle.switch_is_active(USE_ROLE_BASED_ACCESS_CONTROL):
        return True
    request = get_request_or_stub()
    decoded_jwt = get_decoded_jwt_from_request(request)

    print(ENTERPRISE_COUPON_ADMIN_ROLE)
    print(decoded_jwt)
    implicit_access = (
        request_user_has_implicit_access_via_jwt(decoded_jwt, ENTERPRISE_COUPON_ADMIN_ROLE) if decoded_jwt else False
    )
    print("implicit_access is...")
    print(implicit_access)

    if not implicit_access:
        return False

    return has_correct_context_for_implicit_access(obj, decoded_jwt, SYSTEM_ENTERPRISE_ADMIN_ROLE)


@rules.predicate
def request_user_has_explicit_access(user, obj):
    """
    Check that if request user has explicit access to `ENTERPRISE_COUPON_ADMIN_ROLE` feature role.
    Returns:
        boolean: whether the request user has access or not
    """
    if not waffle.switch_is_active(USE_ROLE_BASED_ACCESS_CONTROL):
        return True
    explicit_access = EcommerceFeatureRoleAssignment.objects.filter(
        user=user,
        role__name=ENTERPRISE_COUPON_ADMIN_ROLE
    ).first()
    if not explicit_access:
        return False

    return has_correct_context_for_explicit_access(user, obj)


rules.add_perm('enterprise.can_view_coupon', request_user_has_implicit_access | request_user_has_explicit_access)
rules.add_perm('enterprise.can_assign_coupon', request_user_has_implicit_access | request_user_has_explicit_access)
