"""
Django rules for enterprise
"""
from __future__ import absolute_import

import logging
from django.core.cache import cache

from oscar.core.loading import get_model
import rules
from ecommerce.invoice.models import Invoice

logger = logging.getLogger(__name__)
Order = get_model('order', 'Order')
Line = get_model('basket', 'Line')
Product = get_model('catalogue', 'Product')


@rules.predicate
def is_enterprise_admin_for_coupon(user, obj):
    """
    Returns whether the user is an an enterprise admin.
    """
    if not user.groups.filter(name='enterprise_admin').exists():
        return False

    user_role_metadata = cache.get('{user_id}:role_metadata'.format(user_id=user.id))
    if not user_role_metadata or 'enterprise_admin' not in user_role_metadata:
        return False

    if isinstance(obj, unicode) and obj in user_role_metadata.get('enterprise_admin', []):
        return True
    elif isinstance(obj, Product):
        invoices = Invoice.objects.filter(
            business_client__enterprise_customer_uuid__in=user_role_metadata.get('enterprise_admin', [])
        )
        orders = Order.objects.filter(id__in=[invoice.order_id for invoice in invoices])
        basket_lines = Line.objects.filter(
            basket_id__in=[order.basket_id for order in orders],
            product=obj,
        )
        if basket_lines.exists():
            return True

    return False


rules.add_perm('enterprise.can_view_coupon', is_enterprise_admin_for_coupon | rules.predicates.is_staff)
rules.add_perm('enterprise.can_assign_coupon', is_enterprise_admin_for_coupon | rules.predicates.is_staff)
