"""
Update effective contract discount percentage and discounted price for order lines created by
Manual Order Offers via the Enrollment API by a given Enterprise Customer UUID
"""


import logging
from decimal import Decimal

from django.core.management import BaseCommand
from oscar.core.loading import get_model

from ecommerce.enterprise.mixins import EnterpriseDiscountMixin
from ecommerce.extensions.order.conditions import ManualEnrollmentOrderDiscountCondition
from ecommerce.programs.custom import class_path

Condition = get_model('offer', 'Condition')
ConditionalOffer = get_model('offer', 'ConditionalOffer')
OrderDiscount = get_model('order', 'OrderDiscount')

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class Command(BaseCommand, EnterpriseDiscountMixin):
    """
    Management command to update the effective_contract_discount_percentage and
    effective_contract_discounted_price price for order lines created by
    Manual Order Offers for a given Enterprise Customer UUID
    """

    def add_arguments(self, parser):
        """ Adds argument(s) to the the command """
        parser.add_argument(
            '--enterprise-customer',
            action='store',
            dest='enterprise_customer',
            default=None,
            required=True,
            help='UUID of an existing enterprise customer.',
            type=str,
        )

        parser.add_argument(
            '--discount-percentage',
            action='store',
            dest='discount_percentage',
            default=None,
            required=True,
            help='The discount to apply to orders as a percentage (0-100).',
            type=float,
        )

    def handle(self, *args, **options):
        enterprise_customer = options['enterprise_customer']
        discount_percentage = options['discount_percentage']
        logger.info(
            'Updating all Manual Orders for Enterprise [%s] to have a discount of [%f].',
            enterprise_customer,
            discount_percentage
        )

        # An enterprise should only have a single ManualEnrollmentOrderDiscountCondition used for
        # API enrollment orders
        condition = Condition.objects.get(
            proxy_class=class_path(ManualEnrollmentOrderDiscountCondition),
            enterprise_customer_uuid=enterprise_customer
        )

        # Using the ConditionalOffer we can then get back to a list of OrderDiscounts and Orders
        offer = ConditionalOffer.objects.get(condition=condition)
        discounts = OrderDiscount.objects.filter(offer_id=offer.id).select_related('order')
        for discount in discounts:
            order = discount.order
            # ManualEnrollment orders only have one order_line per order, so no need to loop over lines here
            self.update_orderline_with_enterprise_discount_metadata(
                order=order,
                line=order.lines.first(),
                discount_percentage=Decimal(discount_percentage),
                is_manual_order=True
            )
