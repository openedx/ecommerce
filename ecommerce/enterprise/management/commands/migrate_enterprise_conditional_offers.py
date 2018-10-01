"""
This command migrates the conditional offers for enterprise coupons to the enterprise conditional offer implementation.
"""
from __future__ import unicode_literals

import logging
import os

from django.core.management import BaseCommand, CommandError
from ecommerce.extensions.voucher.models import Voucher
from ecommerce.programs.custom import get_model, class_path, create_condition
from ecommerce.enterprise.conditions import EnterpriseCustomerCondition
from ecommerce.enterprise.utils import get_enterprise_customer
from ecommerce.enterprise.constants import BENEFIT_MAP

Condition = get_model('offer', 'Condition')
Benefit = get_model('offer', 'Benefit')
ConditionalOffer = get_model('offer', 'ConditionalOffer')

logger = logging.getLogger(__name__)

# add batch offset support
# add logging and error handling
# write tests
# deploy to business sandbox and test there

class Command(BaseCommand):
    """
    Creates enrollment codes for courses.
    """

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
            '--batch-sleep',
            action='store',
            dest='batch_sleep',
            default=10,
            help='How long to sleep between batches.',
            type=int,
        )

    def handle(self, *args, **options):
        batch_limit = options['batch_limit']
        batch_sleep = options['batch_sleep']
        # batch_offset =

        total_vouchers = 0

        vouchers = Voucher.objects.all()[0:batch_limit]
        while len(vouchers) > 0:
            total_vouchers += len(vouchers)
            for voucher in vouchers:
                offer = voucher.offers.first()
                if not offer.condition.range.enterprise_customer:
                    continue

                enterprise_customer_uuid = offer.condition.range.enterprise_customer
                enterprise_customer = get_enterprise_customer(offer.site, enterprise_customer_uuid)
                enterprise_customer_name = enterprise_customer['name']
                new_condition = Condition.objects.get_or_create(
                    proxy_class=class_path(EnterpriseCustomerCondition),
                    enterprise_customer_uuid=enterprise_customer_uuid,
                    enterprise_customer_name=enterprise_customer_name,
                    enterprise_customer_catalog_uuid=offer.condition.range.enterprise_customer_catalog,
                    type=Condition.COUNT,
                    value=1,
                )

                new_benefit = Benefit.objects.get_or_create(
                    proxy_class=class_path(BENEFIT_MAP[offer.benefit.type]),
                    value=offer.benefit.value
                )

                new_offer = ConditionalOffer.objects.get_or_create(
                    name=offer.name,
                    offer_type=ConditionalOffer.VOUCHER,
                    condition=new_condition,
                    benefit=new_benefit,
                    max_global_applications=offer.max_global_applications,
                    email_domains=offer.email_domains,
                    site=offer.site,
                    partner=offer.partner,
                    # For initial creation, we are setting the priority lower so that we don't want to use these
                    #  until we've done some other implementation work. We will update this to a higher value later.
                    priority=5,
                )

                voucher.offers.add(new_offer)
                voucher.save()

            vouchers = Voucher.objects.all()[total_vouchers:total_vouchers+batch_limit]
