# encoding: utf-8
"""Contains the tests for migrate enterprise conditional offers command."""

from __future__ import unicode_literals

import logging

from faker import Factory as FakerFactory
from oscar.test.factories import (
    BenefitFactory,
    ConditionalOfferFactory,
    ConditionFactory,
    RangeFactory,
    VoucherFactory
)

from ecommerce.programs.custom import get_model
from ecommerce.tests.testcases import TestCase

Benefit = get_model('offer', 'Benefit')
Condition = get_model('offer', 'Condition')
ConditionalOffer = get_model('offer', 'ConditionalOffer')
Range = get_model('offer', 'Range')
Voucher = get_model('voucher', 'Voucher')

logger = logging.getLogger(__name__)
FAKER = FakerFactory.create()
LOGGER_NAME = 'ecommerce.enterprise.management.commands.migrate_enterprise_conditional_offers'


class MigrateEnterpriseConditionalOffersTests(TestCase):
    """
    Tests the enrollment code creation command.
    """

    def setUp(self):
        """
        Create test data.
        """
        super(MigrateEnterpriseConditionalOffersTests, self).setUp()

        # Set up vouchers that relate to a range with a enterprise_customer
        uuid = '123e4567-e89b-12d3-a456-426655440000'
        range_with_ent_customer = RangeFactory(enterprise_customer=uuid)
        condition = ConditionFactory(range=range_with_ent_customer)
        benefit_percent = BenefitFactory(
            range=range_with_ent_customer,
            type='Percentage',
            value=10.00,
        )
        benefit_absolute = BenefitFactory(
            range=range_with_ent_customer,
            type='Absolute',
            value=47,
        )
        for i in range(2):
            conditional_offer = ConditionalOfferFactory(
                condition=condition,
                benefit=benefit_percent,
                name=FAKER.name(),
            )
            code = '{}EntUserPercentBenefit'.format(i)
            voucher = VoucherFactory(code=code)
            voucher.offers.add(conditional_offer)
        for i in range(2):
            conditional_offer = ConditionalOfferFactory(
                condition=condition,
                benefit=benefit_absolute,
                name=FAKER.name(),
            )
            code = '{}EntUserAbsoluteBenefit'.format(i)
            voucher = VoucherFactory(code=code)
            voucher.offers.add(conditional_offer)

        # Set up vouchers that do not relate to a range with an enterprise_customer
        range_no_ent_customer = RangeFactory()
        condition = ConditionFactory(range=range_no_ent_customer)
        benefit = BenefitFactory(
            range=range_no_ent_customer,
            type='Percentage',
            value=10.00,
        )
        for i in range(3):
            conditional_offer = ConditionalOfferFactory(
                condition=condition,
                benefit=benefit,
                name=FAKER.name(),
            )
            code = '{}NoEntUserPercentBenefit'.format(i)
            voucher = VoucherFactory(code=code)
            voucher.offers.add(conditional_offer)

        assert Voucher.objects.filter(
            offers__condition__range__enterprise_customer__isnull=False
        ).count() == 4

        assert Voucher.objects.filter(
            offers__condition__range__enterprise_customer__isnull=True
        ).count() == 3

    def test_migrate_voucher(self):
        # test cases include: percentage discount, absolute discount, with enterprise catalog,
        pass

    def test_get_voucher_batch(self):
        # test cases include filtering out non enterprise vouchers and getting the correct inidices
        pass

    def test_handle(self):
        # test cases include handling an error, starting from a non default batch offset
        pass
