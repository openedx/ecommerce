"""
Django rules for enterprise
"""
from __future__ import absolute_import

from django.core.cache import cache
from django.conf import settings
import rules
from ecommerce.invoice.models import Invoice


@rules.predicate
def is_enterprise_admin_for_coupon(user, coupon):
    """
    Returns whether the user is an an enterprise admin.
    """
    if not user.groups.filter(name='enterprise_admin').exists():
        return False

    user_role_metadata = cache.get('{user_id}:role_metadata'.format(user_id=user.id))
    coupon_invoice = Invoice.objects.filter(order__basket__lines__order__product_id=coupon.id)
    if coupon_invoice.business_client.enterprise_customer_uuid in user_role_metadata['enterprise_admin']:
        return True

    return False


rules.add_perm('enterprise.can_view_coupon', is_enterprise_admin_for_coupon | rules.predicates.is_staff)
rules.add_perm('enterprise.can_assign_coupon', is_enterprise_admin_for_coupon | rules.predicates.is_staff)
