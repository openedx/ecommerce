

import csv
import os
import tempfile

from django.core.management import call_command
from oscar.core.loading import get_model

from ecommerce.coupons.tests.mixins import CouponMixin
from ecommerce.extensions.offer.models import OFFER_PRIORITY_MANUAL_ORDER
from ecommerce.extensions.test import factories
from ecommerce.tests.testcases import TestCase

ConditionalOffer = get_model('offer', 'ConditionalOffer')


class UpdateEnterpriseOfferOpportunityIdCommandTests(CouponMixin, TestCase):
    """
    Test the `update_enterprise_offer_opportunity_id` command.
    """
    def setUp(self):
        super(UpdateEnterpriseOfferOpportunityIdCommandTests, self).setUp()

        self.enterprise_customer = '1e57ef1f-c96b-47dd-9a7e-0bb24022ede5'
        self.incorrect_opportunity_id = '0060M00000a2cjlRBB'
        self.correct_opportunity_id = '0060M00000a2asdSZZ'

        factories.ManualEnrollmentOrderOfferFactory(
            condition=factories.ManualEnrollmentOrderDiscountConditionFactory(
                enterprise_customer_uuid=self.enterprise_customer
            ),
            sales_force_id=self.incorrect_opportunity_id
        )

    def create_input_data_csv(self):
        """Create csv with enterprise uuid and opportunity id"""
        tmp_csv_path = os.path.join(tempfile.gettempdir(), 'data.csv')

        with open(tmp_csv_path, 'w') as csv_file:  # pylint: disable=unspecified-encoding
            csv_writer = csv.DictWriter(csv_file, fieldnames=['enterprise_uuid', 'opportunity_id'])
            csv_writer.writeheader()
            csv_writer.writerow({
                'enterprise_uuid': self.enterprise_customer,
                'opportunity_id': self.correct_opportunity_id,
            })

        return tmp_csv_path

    def test_update_enterprise_offer_opportunity_id(self):
        """
        Test that manual enrollment order offer has been updated with correct opportunity id.
        """
        csv_file_path = self.create_input_data_csv()

        offer = ConditionalOffer.objects.get(
            offer_type=ConditionalOffer.USER,
            priority=OFFER_PRIORITY_MANUAL_ORDER,
            condition__enterprise_customer_uuid=self.enterprise_customer
        )
        self.assertEqual(offer.sales_force_id, self.incorrect_opportunity_id)

        call_command(
            'update_enterprise_offer_opportunity_id', '--data-csv={}'.format(csv_file_path)
        )

        offer = ConditionalOffer.objects.get(
            offer_type=ConditionalOffer.USER,
            priority=OFFER_PRIORITY_MANUAL_ORDER,
            condition__enterprise_customer_uuid=self.enterprise_customer
        )
        self.assertEqual(offer.sales_force_id, self.correct_opportunity_id)
