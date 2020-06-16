"""
This command change priority of conditional offers.
"""


import logging

from django.core.management import BaseCommand
from oscar.core.loading import get_model

from ecommerce.core.constants import COUPON_PRODUCT_CLASS_NAME

ConditionalOffer = get_model('offer', 'ConditionalOffer')
Product = get_model('catalogue', 'Product')
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Populate enterprise_id for coupon products.

    Example:

        ./manage.py change_priority_of_offers
    """

    help = "Populate enterprise_id for coupon products."

    def add_arguments(self, parser):
        parser.add_argument(
            '--offset',
            dest='offset',
            default=0,
            help='index to start from.',
            type=int,
        )
        parser.add_argument(
            '--limit',
            dest='limit',
            default=100,
            help='Number of coupons to update.',
            type=int,
        )

    def handle(self, *args, **options):
        limit = options['limit']
        offset = options['offset']

        try:
            coupon_products = Product.objects.filter(
                product_class__name=COUPON_PRODUCT_CLASS_NAME,
                coupon_vouchers__vouchers__offers__condition__enterprise_customer_uuid__isnull=False,
            ).distinct().order_by('id')

            count = coupon_products.count()
            logger.info('Found %d coupon products to update.', count)

            while offset < count:
                coupon_product_batch = coupon_products[offset:offset + limit]
                logger.info('Processing batch from index %d to %d', offset, offset + limit)
                for coupon in coupon_product_batch:
                    vouchers = coupon.attr.coupon_vouchers.vouchers
                    enterprise_id = vouchers.first().enterprise_offer.condition.enterprise_customer_uuid
                    coupon.attr.enterprise_customer_uuid = str(enterprise_id)
                    coupon.save()
                    logger.info('Setting enterprise id product attribute for Product %d to value %s',
                                coupon.id, enterprise_id)

                offset += limit

        except Exception as exc:  # pylint: disable=broad-except
            logger.exception('Command execution failed while executing batch %d,%d\n%s', offset, limit, exc)
