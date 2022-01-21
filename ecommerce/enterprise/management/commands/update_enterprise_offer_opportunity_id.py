"""
Update opportunity id for specific enterprise manual enrollment order offers.
"""

import csv
import logging
from uuid import UUID

from django.core.management import BaseCommand

from ecommerce.extensions.offer.models import OFFER_PRIORITY_MANUAL_ORDER
from ecommerce.programs.custom import get_model

ConditionalOffer = get_model('offer', 'ConditionalOffer')

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class Command(BaseCommand):
    """
    Update opportunity id for specific enterprise manual enrollment order offers.

    Read enterprise uuid and its opportunity for a CSV and update the data accordingly.

    Management command can be executed like below
    >>> ./manage.py update_enterprise_offer_opportunity_id --data-csv data.csv
    """
    def add_arguments(self, parser):
        parser.add_argument(
            '--data-csv',
            action='store',
            dest='data_csv',
            help='Path of csv to read enterprise uuids and opportunity ids.',
            type=str,
            required=True,
        )

    def handle(self, *args, **options):
        logger.info('[UPDATE_ENT_OFFER_OPPORTUNITY_ID] Started update of opportunity id.')

        with open(options['data_csv']) as csv_file:  # pylint: disable=unspecified-encoding
            reader = csv.DictReader(csv_file)
            for row in reader:
                manual_order_enterprise_offer = ConditionalOffer.objects.get(
                    offer_type=ConditionalOffer.USER,
                    priority=OFFER_PRIORITY_MANUAL_ORDER,
                    condition__enterprise_customer_uuid=UUID(row['enterprise_uuid']),
                )
                logger.info(
                    '[UPDATE_ENT_OFFER_OPPORTUNITY_ID] Offer: [%s], Old Opportunity ID: [%s], New Opportunity ID: [%s]',
                    manual_order_enterprise_offer.name,
                    manual_order_enterprise_offer.sales_force_id,
                    row['opportunity_id']
                )
                manual_order_enterprise_offer.sales_force_id = row['opportunity_id']
                manual_order_enterprise_offer.save()

        logger.info('[UPDATE_ENT_OFFER_OPPORTUNITY_ID] Finished update of opportunity id.')
