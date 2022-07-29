from uuid import uuid4

import ddt
import mock
from oscar.core.loading import get_model

from ecommerce.extensions.api.serializers import EnterpriseLearnerOfferApiSerializer
from ecommerce.extensions.test import factories as extended_factories
from ecommerce.tests.factories import UserFactory
from ecommerce.tests.testcases import TestCase

OfferAssignment = get_model('offer', 'OfferAssignment')
Voucher = get_model('voucher', 'Voucher')


@ddt.ddt
class EnterpriseLearnerOfferApiSerializerTests(TestCase):

    @ddt.data(
        (100, '74.5'),
        (None, None)
    )
    @ddt.unpack
    @mock.patch('ecommerce.extensions.api.serializers.sum_user_discounts_for_offer')
    def test_serialize_remaining_balance_for_user(
        self,
        max_user_discount,
        expected_remaining_balance,
        mock_sum_user_discounts_for_offer
    ):
        mock_sum_user_discounts_for_offer.return_value = 25.5
        enterprise_customer_uuid = str(uuid4())
        condition = extended_factories.EnterpriseCustomerConditionFactory(
            enterprise_customer_uuid=enterprise_customer_uuid
        )
        enterprise_offer = extended_factories.EnterpriseOfferFactory.create(
            partner=self.partner,
            condition=condition,
            max_user_discount=max_user_discount
        )
        serializer = EnterpriseLearnerOfferApiSerializer(
            data=enterprise_offer,
            context={
                'request': mock.MagicMock(user=UserFactory())
            }
        )
        data = serializer.to_representation(enterprise_offer)
        assert data['remaining_balance_for_user'] == expected_remaining_balance
