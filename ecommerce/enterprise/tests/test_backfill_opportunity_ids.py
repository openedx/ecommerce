

import csv
import os
import tempfile

from django.core.management import call_command
from oscar.core.loading import get_model

from ecommerce.core.constants import COUPON_PRODUCT_CLASS_NAME
from ecommerce.coupons.tests.mixins import CouponMixin
from ecommerce.extensions.offer.models import OFFER_PRIORITY_ENTERPRISE, OFFER_PRIORITY_MANUAL_ORDER
from ecommerce.extensions.test import factories
from ecommerce.tests.testcases import TestCase

ConditionalOffer = get_model('offer', 'ConditionalOffer')
Product = get_model('catalogue', 'Product')


class BackfillOpportunityIdsCommandTests(CouponMixin, TestCase):
    """
    Test the `backfill_opportunity_ids` command.
    """
    def setUp(self):
        super(BackfillOpportunityIdsCommandTests, self).setUp()

        # coupons and offers created for these enterprises are missing opportunity ids in database
        self.enterprise_without_opportunity_ids = {
            'af4b351f-5f1c-4fc3-af41-48bb38fcb161': 'sf100',
            '8212a8d8-c6b1-4023-8754-4d687c43d72f': 'sf200',
        }

        # coupons and offers created for these enterprise have the opportunity id
        self.enterprise_with_opportunity_id = ('68c7b796-3d9c-4038-a870-3b5eb75c5d39', 'sf999')

        # create enterprise coupons, enterprise offers and manual orders without opportunity id
        for enterprise_customer, __ in self.enterprise_without_opportunity_ids.items():
            self.init_data(enterprise_customer)

        # create an enterprise coupon, enterprise offer and manual order offer with opportunity id
        self.init_data(
            self.enterprise_with_opportunity_id[0],
            self.enterprise_with_opportunity_id[1],
        )

        # multi contracts data setup for coupons and offers
        self.multi_contract_vouchers = [
            ['0a434fa0-2edb-416a-ba24-0d504cc8f6d2', 1345, 'Voucher', 3000, 'OID400'],
            ['0a434fa0-2edb-416a-ba24-0d504cc8f6d2', 2876, 'Voucher', 3000, 'OID400'],
            ['0a434fa0-2edb-416a-ba24-0d504cc8f6d2', 9034, 'Voucher', 3000, 'OID450'],
            ['0a434fa0-2edb-416a-ba24-0d504cc8f6d2', 2223, 'Voucher', 3001, 'OID444'],
        ]

        created = []
        for record in self.multi_contract_vouchers:
            if record[3] not in created:
                created.append(record[3])
                coupon = self.create_coupon(enterprise_customer=record[0])
                coupon.id = record[3]
                coupon.save()

        self.multi_contract_ent_offers = [
            ['56b250c3-0050-47da-819c-e677fb8c03be', 4000, 'Site', '', 'OID500'],
            ['56b250c3-0050-47da-819c-e677fb8c03be', 4000, 'Site', '', 'OID500'],
            ['56b250c3-0050-47da-819c-e677fb8c03be', 4000, 'Site', '', 'OID550'],
            ['56b250c3-0050-47da-819c-e677fb8c03be', 4001, 'Site', '', 'OID555'],
        ]
        created = []
        for record in self.multi_contract_ent_offers:
            if record[1] not in created:
                created.append(record[1])
                factories.EnterpriseOfferFactory(
                    id=record[1],
                    condition=factories.EnterpriseCustomerConditionFactory(
                        enterprise_customer_uuid=record[0]
                    )
                )

        self.multi_contract_manual_offers = [
            ['1204f563-ef3d-47cb-85c4-f67de61c5733', 6000, 'User', '', 'OID600'],
            ['1204f563-ef3d-47cb-85c4-f67de61c5733', 6000, 'User', '', 'OID600'],
            ['1204f563-ef3d-47cb-85c4-f67de61c5733', 6000, 'User', '', 'OID650'],
            ['1204f563-ef3d-47cb-85c4-f67de61c5733', 6001, 'User', '', 'OID666'],
        ]
        created = []
        for record in self.multi_contract_manual_offers:
            if record[1] not in created:
                created.append(record[1])
                factories.ManualEnrollmentOrderOfferFactory(
                    id=record[1],
                    condition=factories.ManualEnrollmentOrderDiscountConditionFactory(
                        enterprise_customer_uuid=record[0]
                    )
                )

        self.multi_contract_enterprises_with_opportunity_ids_only = [
            ['1e57ef1f-c96b-47dd-9a7e-0bb24022ede5', '', '', '', 'OID700'],
            ['11e0a60d-0f79-4d96-a55b-4e126cb34a51', '', '', '', 'OID800'],
            ['9b951dd8-4bbd-4b5b-9186-c4bee1c96e1a', '', '', '', 'OID900'],
        ]
        for record in self.multi_contract_enterprises_with_opportunity_ids_only:
            self.init_data(record[0])

    def init_data(self, enterprise_customer, opportunity_id=None):
        """
        Create database records to test against.
        """
        self.create_coupon(enterprise_customer=enterprise_customer, sales_force_id=opportunity_id)

        factories.EnterpriseOfferFactory(
            condition=factories.EnterpriseCustomerConditionFactory(
                enterprise_customer_uuid=enterprise_customer
            ),
            sales_force_id=opportunity_id
        )

        factories.ManualEnrollmentOrderOfferFactory(
            condition=factories.ManualEnrollmentOrderDiscountConditionFactory(
                enterprise_customer_uuid=enterprise_customer
            ),
            sales_force_id=opportunity_id
        )

    def create_input_data_csv(self):
        """Create csv with enterprise uuid and opportunity id"""
        tmp_csv_path = os.path.join(tempfile.gettempdir(), 'data.csv')

        with open(tmp_csv_path, 'w') as csv_file:
            csv_writer = csv.DictWriter(csv_file, fieldnames=['enterprise_customer_uuid', 'opportunity_id'])
            csv_writer.writeheader()
            for enterprise_customer, opportunity_id in self.enterprise_without_opportunity_ids.items():
                csv_writer.writerow({
                    'enterprise_customer_uuid': enterprise_customer,
                    'opportunity_id': opportunity_id,
                })

            # add those enterprise uuids that already have opportunity ids set in database
            # this is to ensure that existing opportunity are not modified by backfilling
            csv_writer.writerow({
                'enterprise_customer_uuid': self.enterprise_with_opportunity_id[0],
                'opportunity_id': self.enterprise_with_opportunity_id[1],
            })

        return tmp_csv_path

    def create_multi_contracts_input_data_csv(self):
        """Create csv for multi contracts"""
        header_row = [
            'ENTERPRISE_CUSTOMER_UUID',
            'ORDER_LINE_OFFER_ID',
            'ORDER_LINE_OFFER_TYPE',
            'ORDER_LINE_COUPON_ID',
            'OPP_ID',
        ]

        tmp_csv_path = os.path.join(tempfile.gettempdir(), 'multi_contracts_data.csv')
        with open(tmp_csv_path, 'w') as csv_file:
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow(header_row)

            # write data for enterprise coupons
            csv_writer.writerows(self.multi_contract_vouchers)

            # write data for enterprise offers
            csv_writer.writerows(self.multi_contract_ent_offers)

            # write data for enterprise manual order offers
            csv_writer.writerows(self.multi_contract_manual_offers)

            # write data for enterprises with opportunity ids only
            csv_writer.writerows(self.multi_contract_enterprises_with_opportunity_ids_only)

        return tmp_csv_path

    def assert_coupon(self, data, extra_filter=None):
        """
        Verify coupon data.
        """
        for enterprise_customer_uuid, opportunity_id in data.items():
            filter_kwargs = {
                'product_class__name': COUPON_PRODUCT_CLASS_NAME,
                'attributes__code': 'enterprise_customer_uuid',
                'attribute_values__value_text': enterprise_customer_uuid
            }
            if extra_filter:
                filter_kwargs = dict(filter_kwargs, **extra_filter)
            coupon = Product.objects.get(**filter_kwargs)
            self.assertEqual(getattr(coupon.attr, 'sales_force_id', None), opportunity_id)

    def assert_enterprise_offer(self, data, extra_filter=None):
        """
        Verify enterprise offer data.
        """
        for enterprise_customer_uuid, opportunity_id in data.items():
            filter_kwargs = {
                'offer_type': ConditionalOffer.SITE,
                'priority': OFFER_PRIORITY_ENTERPRISE,
                'condition__enterprise_customer_uuid': enterprise_customer_uuid
            }
            if extra_filter:
                filter_kwargs = dict(filter_kwargs, **extra_filter)
            offer = ConditionalOffer.objects.get(**filter_kwargs)
            self.assertEqual(offer.sales_force_id, opportunity_id)

    def assert_manual_order_offer(self, data, extra_filter=None):
        """
        Verify manual offer data.
        """
        for enterprise_customer_uuid, opportunity_id in data.items():
            filter_kwargs = {
                'offer_type': ConditionalOffer.USER,
                'priority': OFFER_PRIORITY_MANUAL_ORDER,
                'condition__enterprise_customer_uuid': enterprise_customer_uuid
            }
            if extra_filter:
                filter_kwargs = dict(filter_kwargs, **extra_filter)
            offer = ConditionalOffer.objects.get(**filter_kwargs)
            self.assertEqual(offer.sales_force_id, opportunity_id)

    def assert_data(self, data):
        """
        Verify data for enterprise couons, enterprise offers and manual order offers
        """
        self.assert_coupon(data)
        self.assert_enterprise_offer(data)
        self.assert_manual_order_offer(data)

    def test_backfill_opportunity_ids(self):
        """
        Test that correct opportunity ids are set for coupons and offers.
        """
        csv_file_path = self.create_input_data_csv()

        call_command(
            'backfill_opportunity_ids', '--data-csv={}'.format(csv_file_path)
        )

        data = dict(self.enterprise_without_opportunity_ids)
        data[self.enterprise_with_opportunity_id[0]] = self.enterprise_with_opportunity_id[1]
        self.assert_data(data)

    def test_backfill_multi_contract_opportunity_ids(self):
        """
        Test that correct opportunity ids are set for coupons and offers for multi contracts.
        """
        csv_file_path = self.create_multi_contracts_input_data_csv()

        call_command(
            'backfill_opportunity_ids', '--data-csv={}'.format(csv_file_path), '--contract-type=multi'
        )

        # verify coupons
        expected_coupon_data = [
            {'0a434fa0-2edb-416a-ba24-0d504cc8f6d2': 'OID400'},
            {'0a434fa0-2edb-416a-ba24-0d504cc8f6d2': 'OID444'},
        ]
        for data, coupon_id in zip(expected_coupon_data, [3000, 3001]):
            self.assert_coupon(data, {'id': coupon_id})

        # verify enterprise offers
        expected_offer_data = [
            {'56b250c3-0050-47da-819c-e677fb8c03be': 'OID500'},
            {'56b250c3-0050-47da-819c-e677fb8c03be': 'OID555'},
        ]
        for data, offer_id in zip(expected_offer_data, [4000, 4001]):
            self.assert_enterprise_offer(data, {'id': offer_id})

        # verify enterprise manual order offers
        expected_offer_data = [
            {'1204f563-ef3d-47cb-85c4-f67de61c5733': 'OID600'},
            {'1204f563-ef3d-47cb-85c4-f67de61c5733': 'OID666'},
        ]
        for data, offer_id in zip(expected_offer_data, [6000, 6001]):
            self.assert_manual_order_offer(data, {'id': offer_id})

        # verify that opportunity ids are set correctly for coupons and
        # offers for enterprises with opportunity ids only in csv
        data = {}
        for record in self.multi_contract_enterprises_with_opportunity_ids_only:
            data[record[0]] = record[-1]
        self.assert_data(data)
