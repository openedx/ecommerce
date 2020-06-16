"""
Backfill opportunity ids for Enterprise Coupons, Enterprise Offers and Manual Order Offers.
"""


import csv
import logging
from collections import Counter, defaultdict
from time import sleep
from uuid import UUID

from django.core.management import BaseCommand

from ecommerce.core.constants import COUPON_PRODUCT_CLASS_NAME
from ecommerce.extensions.offer.models import OFFER_PRIORITY_ENTERPRISE, OFFER_PRIORITY_MANUAL_ORDER
from ecommerce.programs.custom import get_model

ConditionalOffer = get_model('offer', 'ConditionalOffer')
Product = get_model('catalogue', 'Product')

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class Command(BaseCommand):
    """
    Backfill opportunity ids for Enterprise Coupons, Enterprise Offers and Manual Order Offers.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--data-csv',
            action='store',
            dest='data_csv',
            default=None,
            help='Path of csv to read enterprise uuids and opportunity ids.',
            type=str,
        )

        parser.add_argument(
            '--contract-type',
            action='store',
            dest='contract_type',
            default='single',
            choices=['single', 'multi'],
            help='Specify type of backfilling',
            type=str,
        )

        parser.add_argument(
            '--batch-limit',
            action='store',
            dest='batch_limit',
            default=100,
            help='Number of records to be fetched in each batch of backfilling.',
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

    def read_csv(self, csv_path):
        data = {}
        with open(csv_path) as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:
                data[UUID(row['enterprise_customer_uuid'])] = row['opportunity_id']

        return data

    def read_multi_contracts_csv(self, csv_path):
        data = {
            'coupons': defaultdict(list),
            'offers': defaultdict(list),
            'ec_uuids': defaultdict(list),
        }
        with open(csv_path) as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:
                if row['ORDER_LINE_OFFER_TYPE'] == 'Voucher':
                    data['coupons'][row['ORDER_LINE_COUPON_ID']].append(row['OPP_ID'])
                elif row['ORDER_LINE_OFFER_TYPE'] in ('Site', 'User'):
                    data['offers'][row['ORDER_LINE_OFFER_ID']].append(row['OPP_ID'])
                else:
                    data['ec_uuids'][UUID(row['ENTERPRISE_CUSTOMER_UUID'])].append(row['OPP_ID'])

        # condition the data so that at the end we have only one opportunity id for each coupon/offer
        for __, category_data in data.items():
            for category_object_id, opportunity_ids in category_data.items():
                if len(opportunity_ids) > 1:
                    most_common_opportunity_id, __ = Counter(opportunity_ids).most_common(1)[0]
                    category_data[category_object_id] = most_common_opportunity_id
                else:
                    category_data[category_object_id] = opportunity_ids[0]

        return data

    def get_enterprise_coupons_batch(self, coupon_filter, start, end):
        logger.info('Fetching new batch of enterprise coupons from indexes: %s to %s', start, end)
        return Product.objects.filter(**coupon_filter)[start:end]

    def get_enterprise_offers_batch(self, offer_filter, start, end):
        return ConditionalOffer.objects.filter(**offer_filter)[start:end]

    def _backfill_enterprise_coupons(self, data, options, coupon_filter):
        batch_limit = options['batch_limit']
        batch_sleep = options['batch_sleep']
        batch_offset = options['batch_offset']
        current_batch_index = batch_offset

        logger.info('Started Backfilling Enterprise Coupons...')

        coupons = self.get_enterprise_coupons_batch(coupon_filter, batch_offset, batch_offset + batch_limit)
        while coupons:
            for coupon in coupons:
                opportunity_id = data.get(str(coupon.id)) or data.get(UUID(coupon.attr.enterprise_customer_uuid))
                if getattr(coupon.attr, 'sales_force_id', None) is None and opportunity_id:
                    logger.info(
                        'Enterprise Coupon updated. CouponID: [%s], OpportunityID: [%s]',
                        coupon.id,
                        opportunity_id
                    )
                    coupon.attr.sales_force_id = opportunity_id
                    coupon.save()

            sleep(batch_sleep)

            current_batch_index += len(coupons)
            coupons = self.get_enterprise_coupons_batch(
                coupon_filter, current_batch_index, current_batch_index + batch_limit
            )

        logger.info('Backfilling for Enterprise Coupons finished.')

    def _backfill_offers(self, data, options, offer_filter, log_prefix):
        logger.info('[%s] Started Backfilling Offers...', log_prefix)

        batch_limit = options['batch_limit']
        batch_sleep = options['batch_sleep']
        batch_offset = options['batch_offset']
        current_batch_index = batch_offset

        ent_offers = self.get_enterprise_offers_batch(offer_filter, batch_offset, batch_offset + batch_limit)
        while ent_offers:
            for ent_offer in ent_offers:
                opportunity_id = data.get(str(ent_offer.id)) or data.get(ent_offer.condition.enterprise_customer_uuid)
                if bool(ent_offer.sales_force_id) is False and opportunity_id:
                    logger.info(
                        '[%s] Offer updated. OfferID: [%s], OpportunityID: [%s]',
                        log_prefix,
                        ent_offer.id,
                        opportunity_id,
                    )
                    ent_offer.sales_force_id = opportunity_id
                    ent_offer.save()

            sleep(batch_sleep)

            current_batch_index += len(ent_offers)
            ent_offers = self.get_enterprise_offers_batch(
                offer_filter, current_batch_index, current_batch_index + batch_limit
            )

        logger.info('[%s] Backfilling for Offers finished.', log_prefix)

    def handle(self, *args, **options):
        if options['contract_type'] == 'single':
            logger.info('Backfilling for single contracts.')
            self.backfill_single_contracts(options)
        elif options['contract_type'] == 'multi':
            logger.info('Backfilling for multi contracts.')
            self.backfill_multi_contracts(options)

    def backfill_single_contracts(self, options):
        data = self.read_csv(options['data_csv'])

        self._backfill_enterprise_coupons(data, options, {
            'product_class__name': COUPON_PRODUCT_CLASS_NAME,
            'attributes__code': 'enterprise_customer_uuid',
            'attribute_values__value_text__in': data.keys()
        })
        self._backfill_offers(data, options, {
            'offer_type': ConditionalOffer.SITE,
            'priority': OFFER_PRIORITY_ENTERPRISE,
            'condition__enterprise_customer_uuid__in': data.keys(),
        }, 'ENTERPRISE OFFER')
        self._backfill_offers(data, options, {
            'offer_type': ConditionalOffer.USER,
            'priority': OFFER_PRIORITY_MANUAL_ORDER,
            'condition__enterprise_customer_uuid__in': data.keys(),
        }, 'ENTERPRISE MANUAL ORDER OFFER')

    def backfill_multi_contracts(self, options):
        data = self.read_multi_contracts_csv(options['data_csv'])

        coupons_data = data['coupons']
        self._backfill_enterprise_coupons(coupons_data, options, {
            'product_class__name': COUPON_PRODUCT_CLASS_NAME,
            'id__in': coupons_data.keys()
        })

        offers_data = data['offers']
        self._backfill_offers(offers_data, options, {
            'offer_type__in': (ConditionalOffer.SITE, ConditionalOffer.USER),
            'priority__in': (OFFER_PRIORITY_ENTERPRISE, OFFER_PRIORITY_MANUAL_ORDER),
            'id__in': offers_data.keys(),
        }, 'ALL ENTERPRISE OFFERS')

        # backfill coupons and offers missing both coupon id and offer id
        ec_uuids = data['ec_uuids']
        self._backfill_enterprise_coupons(ec_uuids, options, {
            'product_class__name': COUPON_PRODUCT_CLASS_NAME,
            'attributes__code': 'enterprise_customer_uuid',
            'attribute_values__value_text__in': ec_uuids.keys()
        })
        self._backfill_offers(ec_uuids, options, {
            'offer_type': ConditionalOffer.SITE,
            'priority': OFFER_PRIORITY_ENTERPRISE,
            'condition__enterprise_customer_uuid__in': ec_uuids.keys(),
        }, 'ENTERPRISE OFFER')
        self._backfill_offers(ec_uuids, options, {
            'offer_type': ConditionalOffer.USER,
            'priority': OFFER_PRIORITY_MANUAL_ORDER,
            'condition__enterprise_customer_uuid__in': ec_uuids.keys(),
        }, 'ENTERPRISE MANUAL ORDER OFFER')
