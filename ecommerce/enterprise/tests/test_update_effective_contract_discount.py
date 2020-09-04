# encoding: utf-8
"""
Contains the tests for updating effective_contract_discount_percentage and discounted_price for order lines created by
Manual Order Offers via the Enrollment API
"""
from decimal import Decimal

from django.core.management import call_command
from mock import patch
from oscar.test.factories import (
    ConditionalOfferFactory,
    ConditionFactory,
    OrderDiscountFactory,
    OrderFactory,
    OrderLineFactory,
    ProductFactory
)

from ecommerce.extensions.test.factories import ManualEnrollmentOrderDiscountConditionFactory
from ecommerce.programs.custom import get_model
from ecommerce.tests.testcases import TestCase

Condition = get_model('offer', 'Condition')
ConditionalOffer = get_model('offer', 'ConditionalOffer')
OrderDiscount = get_model('order', 'OrderDiscount')
OrderLine = get_model('order', 'Line')


class UpdateEffectiveContractDiscountTests(TestCase):
    """
    Tests the enrollment code creation command.
    """

    def setUp(self):
        """
        Create test data.
        """
        super(UpdateEffectiveContractDiscountTests, self).setUp()

        # Set up orders with a enterprise_customer
        self.enterprise_customer_uuid = '123e4567-e89b-12d3-a456-426655440000'
        self.unit_price = 100
        self.condition = ManualEnrollmentOrderDiscountConditionFactory(enterprise_customer_uuid=self.enterprise_customer_uuid)
        self.offer = ConditionalOfferFactory(condition=self.condition, id=9999)
        self.order = OrderFactory()
        self.order_discount = OrderDiscountFactory(offer_id=self.offer.id, order=self.order)
        self.line = OrderLineFactory(order=self.order, unit_price_excl_tax=self.unit_price)
        self.line.save()
        self.order_discount = OrderDiscountFactory(offer_id=self.offer.id, order=self.order)
        self.order.save()
        self.offer.save()
        self.condition.save()

    def test_discount_update(self):
        discount_percentage = 20
        call_command(
            'seed_enterprise_devstack_data',
            '--enterprise-customer={} --discount_percentage={}'.format(
                self.enterprise_customer_uuid,
                discount_percentage
            )
        )
        assert self.line.effective_contract_discount_percentage == 20
        assert self.line.effective_contract_discounted_price == self.unit_price * (discount_percentage * Decimal('.01'))
