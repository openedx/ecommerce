# encoding: utf-8
"""Contains the tests for migrate enterprise conditional offers command."""
import logging

from django.core.management import call_command
from mock import patch
from oscar.test.factories import (
    BenefitFactory,
    ConditionalOfferFactory,
    ConditionFactory,
    RangeFactory,
    VoucherFactory
)

from ecommerce.enterprise.management.commands.migrate_enterprise_conditional_offers import Command
from ecommerce.programs.custom import get_model
from ecommerce.tests.testcases import TestCase

Benefit = get_model('offer', 'Benefit')
Condition = get_model('offer', 'Condition')
ConditionalOffer = get_model('offer', 'ConditionalOffer')
Range = get_model('offer', 'Range')
Voucher = get_model('voucher', 'Voucher')

logger = logging.getLogger(__name__)
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
            code = '{}EntUserPercentBenefit'.format(i)
            voucher = VoucherFactory(code=code)
            offer_name = "Coupon [{}]-{}-{}".format(
                voucher.pk,
                benefit_percent.type,
                benefit_percent.value
            )
            conditional_offer = ConditionalOfferFactory(
                condition=condition,
                benefit=benefit_percent,
                name=offer_name,
            )
            voucher.offers.add(conditional_offer)

        for i in range(2):
            code = '{}EntUserAbsoluteBenefit'.format(i)
            voucher = VoucherFactory(code=code)
            offer_name = "Coupon [{}]-{}-{}".format(
                voucher.pk,
                benefit_absolute.type,
                benefit_absolute.value
            )
            conditional_offer = ConditionalOfferFactory(
                condition=condition,
                benefit=benefit_absolute,
                name=offer_name,
            )
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
            code = '{}NoEntUserPercentBenefit'.format(i)
            voucher = VoucherFactory(code=code)
            offer_name = "Coupon [{}]-{}-{}".format(
                voucher.pk,
                benefit.type,
                benefit.value
            )
            conditional_offer = ConditionalOfferFactory(
                condition=condition,
                benefit=benefit,
                name=offer_name,
            )
            voucher.offers.add(conditional_offer)

        assert Voucher.objects.filter(
            offers__condition__range__enterprise_customer__isnull=False
        ).count() == 4

        assert Voucher.objects.filter(
            offers__condition__range__enterprise_customer__isnull=True
        ).count() == 3

        self.command = Command()

    def test_migrate_voucher(self):
        """
        _migrate_voucher should create new conditional offers for vouchers
        that ultimately relate to an enterprise_customer
        """
        voucher = Voucher.objects.filter(
            offers__condition__range__enterprise_customer__isnull=False
        ).first()

        assert voucher.offers.count() == 1

        with patch('ecommerce.enterprise.management'
                   '.commands.migrate_enterprise_conditional_offers'
                   '.Command._get_enterprise_customer') as mock_get_ent_customer:
            mock_get_ent_customer.return_value = {'name': 'Boo Radley'}
            self.command._migrate_voucher(voucher)  # pylint: disable=protected-access

        voucher.refresh_from_db()
        assert voucher.offers.count() == 2
        assert voucher.offers.get(name__contains='ENT Offer').offer_type == ConditionalOffer.VOUCHER

    def test_get_enterprise_customer(self):
        """
        _get_enterprise_customer should return the correct value for enterprise
        customer that is stored in the command's enterprise_customer_map
        """
        enterprise_customer_uuid = "some uuid"
        site = "some site"
        with patch('ecommerce.enterprise.management.commands'
                   '.migrate_enterprise_conditional_offers'
                   '.get_enterprise_customer') as mock_get_customer:
            mock_get_customer.return_value = 'Hannah Dee'
            # pylint: disable=protected-access
            actual = self.command._get_enterprise_customer(enterprise_customer_uuid, site)
        assert actual == 'Hannah Dee'

    def test_get_voucher_batch(self):
        """
        _get_voucher_batch should return the correct query_set based on start
        and end inidices provided
        """
        start = 2
        end = 5
        expected_query = str(
            Voucher.objects.filter(offers__condition__range__enterprise_customer__isnull=False)[start:end].query
        )
        actual_query = str(self.command._get_voucher_batch(start, end).query)  # pylint: disable=protected-access
        assert actual_query == expected_query

    def test_handle(self):
        """
        handle should create new conditional offers for all voucher objects
        that ultimately relate to a range that has an enterprise_customer
        """
        # The dynamic conditional offer is added in a migration, so it should already
        # be in the database.
        offers = ConditionalOffer.objects.exclude(name='dynamic_conditional_offer')
        assert offers.count() == 7
        assert offers.filter(name__contains='ENT Offer').count() == 0

        for voucher in Voucher.objects.all():
            assert voucher.offers.count() == 1

        with patch('ecommerce.enterprise.management'
                   '.commands.migrate_enterprise_conditional_offers'
                   '.Command._get_enterprise_customer') as mock_get_ent_customer:
            mock_get_ent_customer.return_value = {'name': 'Boo Radley'}
            call_command('migrate_enterprise_conditional_offers', batch_sleep=0)

        offers = ConditionalOffer.objects.exclude(name='dynamic_conditional_offer')
        assert offers.count() == 11
        assert offers.filter(name__contains='ENT Offer').count() == 4

        # Targets the original set of vouchers that have an enterprise_customer
        # value on a range they are related to
        vouchers = Voucher.objects.filter(
            offers__condition__range__enterprise_customer__isnull=False
        )
        for voucher in vouchers:
            assert voucher.offers.count() == 2

        # The inverse of this same query returns a set of vouchers that we hoped
        # not to process. We should be then able to assert that there is only
        # one offer per one of these vouchers
        vouchers = Voucher.objects.exclude(
            offers__condition__range__enterprise_customer__isnull=False
        )
        for voucher in vouchers:
            assert voucher.offers.count() == 1

    def test_handle_non_default_settings(self):
        """
        handle should create new conditional offers for voucher objects
        that ultimately relate to a range that has an enterprise_customer
        for a different subset of vouchers
        """
        offers = ConditionalOffer.objects.exclude(name='dynamic_conditional_offer')
        assert offers.count() == 7
        assert offers.filter(name__contains='ENT Offer').count() == 0

        for voucher in Voucher.objects.all():
            assert voucher.offers.count() == 1

        with patch('ecommerce.enterprise.management'
                   '.commands.migrate_enterprise_conditional_offers'
                   '.Command._get_enterprise_customer') as mock_get_ent_customer:
            mock_get_ent_customer.return_value = {'name': 'Boo Radley'}
            call_command(
                'migrate_enterprise_conditional_offers',
                batch_sleep=0,
                batch_limit=58,
                batch_offset=3,  # 3rd index is the 4th item
            )

        offers = ConditionalOffer.objects.exclude(name='dynamic_conditional_offer')
        assert offers.count() == 8
        assert offers.filter(name__contains='ENT Offer').count() == 1

    def test_handle_error(self):
        """
        handle should raise error if something goes wrong during batch
        processing of vouchers
        """
        with patch('ecommerce.enterprise.management'
                   '.commands.migrate_enterprise_conditional_offers'
                   '.Command._get_voucher_batch') as mock_get_voucher:
            mock_get_voucher.side_effect = IndexError()
            with self.assertRaises(Exception):
                call_command('migrate_enterprise_conditional_offers')
