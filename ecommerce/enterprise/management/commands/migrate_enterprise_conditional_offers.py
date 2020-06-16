"""
This command migrates the conditional offers for enterprise coupons to the enterprise conditional offer implementation.
"""


import logging
from time import sleep

from django.contrib.sites.models import Site
from django.core.management import BaseCommand

from ecommerce.enterprise.benefits import BENEFIT_MAP
from ecommerce.enterprise.conditions import EnterpriseCustomerCondition
from ecommerce.enterprise.utils import get_enterprise_customer
from ecommerce.extensions.offer.models import OFFER_PRIORITY_VOUCHER
from ecommerce.extensions.voucher.models import Voucher
from ecommerce.programs.custom import class_path, get_model

Condition = get_model('offer', 'Condition')
Benefit = get_model('offer', 'Benefit')
ConditionalOffer = get_model('offer', 'ConditionalOffer')

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Migrates conditional offers for enterprise coupons to enterprise conditional offer implementation.
    """

    site = None
    enterprise_customer_map = {}
    help = ('This command migrates the conditional offers for enterprise coupons '
            'to the enterprise conditional offer implementation.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-limit',
            action='store',
            dest='batch_limit',
            default=100,
            help='Number of vouchers in each batch of conditional offer migration.',
            type=int,
        )

        parser.add_argument(
            '--batch-offset',
            action='store',
            dest='batch_offset',
            default=0,
            help='Which index to start batching from.',
            type=int,
        )

        parser.add_argument(
            '--batch-sleep',
            action='store',
            dest='batch_sleep',
            default=10,
            help='How long to sleep between batches.',
            type=int,
        )

    def _get_default_site(self):
        if not self.site:
            self.site = Site.objects.get(id=1)

        return self.site

    def _get_enterprise_customer(self, enterprise_customer_uuid, site):
        if enterprise_customer_uuid not in self.enterprise_customer_map:
            enterprise_customer = get_enterprise_customer(site, enterprise_customer_uuid)
            self.enterprise_customer_map[enterprise_customer_uuid] = enterprise_customer

        return self.enterprise_customer_map[enterprise_customer_uuid]

    def _migrate_voucher(self, voucher):
        offer = voucher.offers.order_by('date_created')[0]
        enterprise_customer_uuid = offer.condition.range.enterprise_customer
        site = offer.site or self._get_default_site()
        enterprise_customer = self._get_enterprise_customer(enterprise_customer_uuid, site)
        enterprise_customer_name = enterprise_customer['name']

        new_condition, _ = Condition.objects.get_or_create(
            proxy_class=class_path(EnterpriseCustomerCondition),
            enterprise_customer_uuid=enterprise_customer_uuid,
            enterprise_customer_name=enterprise_customer_name,
            enterprise_customer_catalog_uuid=offer.condition.range.enterprise_customer_catalog,
            type=Condition.COUNT,
            value=1,
        )

        new_benefit, _ = Benefit.objects.get_or_create(
            proxy_class=class_path(BENEFIT_MAP[offer.benefit.type]),
            value=offer.benefit.value,
            max_affected_items=offer.benefit.max_affected_items,
        )

        offer_name = offer.name + " ENT Offer"
        new_offer, _ = ConditionalOffer.objects.get_or_create(
            name=offer_name,
            offer_type=ConditionalOffer.VOUCHER,
            condition=new_condition,
            benefit=new_benefit,
            max_global_applications=offer.max_global_applications,
            email_domains=offer.email_domains,
            site=offer.site,
            partner=offer.partner,
            priority=OFFER_PRIORITY_VOUCHER,
        )

        voucher.offers.add(new_offer)
        voucher.save()

    def _get_voucher_batch(self, start, end):
        logger.info('Fetching new batch of vouchers from indexes: %s to %s', start, end)
        return Voucher.objects.filter(offers__condition__range__enterprise_customer__isnull=False)[start:end]

    def handle(self, *args, **options):
        batch_limit = options['batch_limit']
        batch_sleep = options['batch_sleep']
        batch_offset = options['batch_offset']

        current_batch_index = batch_offset
        logger.info('Starting migration of enterprise conditional offers!')

        try:
            vouchers = self._get_voucher_batch(batch_offset, batch_offset + batch_limit)
            while vouchers:
                for index, voucher in enumerate(vouchers):
                    logger.info('Processing Voucher with index %s and id %s', current_batch_index + index, voucher.id)
                    self._migrate_voucher(voucher)

                sleep(batch_sleep)
                current_batch_index += len(vouchers)
                vouchers = self._get_voucher_batch(current_batch_index, current_batch_index + batch_limit)
        except Exception:  # pylint: disable=broad-except
            logger.exception('Script execution failed!')
            raise

        logger.info('Successfully finished migrating enterprise conditional offers!')
