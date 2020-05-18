from __future__ import absolute_import

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

    def assert_coupon(self, data):
        """
        Verify coupon data.
        """
        for enterprise_customer_uuid, opportunity_id in data.items():
            filter_kwargs = {
                'product_class__name': COUPON_PRODUCT_CLASS_NAME,
                'attributes__code': 'enterprise_customer_uuid',
                'attribute_values__value_text': enterprise_customer_uuid
            }
            coupon = Product.objects.get(**filter_kwargs)
            self.assertEqual(getattr(coupon.attr, 'sales_force_id', None), opportunity_id)

    def assert_enterprise_offer(self, data):
        """
        Verify enterprise offer data.
        """
        for enterprise_customer_uuid, opportunity_id in data.items():
            offer = ConditionalOffer.objects.get(**{
                'offer_type': ConditionalOffer.SITE,
                'priority': OFFER_PRIORITY_ENTERPRISE,
                'condition__enterprise_customer_uuid': enterprise_customer_uuid
            })
            self.assertEqual(offer.sales_force_id, opportunity_id)

    def assert_manual_order_offer(self, data):
        """
        Verify manual offer data.
        """
        for enterprise_customer_uuid, opportunity_id in data.items():
            offer = ConditionalOffer.objects.get(**{
                'offer_type': ConditionalOffer.USER,
                'priority': OFFER_PRIORITY_MANUAL_ORDER,
                'condition__enterprise_customer_uuid': enterprise_customer_uuid
            })
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
