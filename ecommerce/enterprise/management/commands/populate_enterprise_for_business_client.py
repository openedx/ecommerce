"""
This command populates the enterprise customer uuid field for BusinessClient where possible.
"""
from __future__ import unicode_literals

import logging

from django.core.management import BaseCommand

from ecommerce.extensions.voucher.models import CouponVouchers
from ecommerce.invoice.models import Invoice

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Populates the enterprise customer uuid field for BusinessClient where possible.
    """

    business_client_map = {}
    help = 'This command populates the enterprise customer uuid field for BusinessClient where possible.'

    def _get_enterprise_coupon_products(self):
        return CouponVouchers.objects.filter(
            vouchers__offers__condition__range__enterprise_customer__isnull=False,
        )

    def handle(self, *args, **options):
        logger.info('Starting migration of enterprise conditional offers!')

        try:
            coupons = self._get_enterprise_coupon_products()
            for coupon in coupons:
                enterprise_customer = coupon.vouchers.first().original_offer.condition.range.enterprise_customer
                business_client = Invoice.objects.get(order__lines__product_id=coupon.id).business_client
                if not self.business_client_map[business_client]:
                    business_client.enterprise_customer_uuid = enterprise_customer
                    business_client.save()
                    self.business_client_map[business_client] = enterprise_customer

        except Exception:  # pylint: disable=broad-except
            logger.exception('Script execution failed!')
            raise

        logger.info('Successfully finished migrating enterprise conditional offers!')
