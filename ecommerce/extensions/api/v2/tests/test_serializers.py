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
        (100, 25.5, '74.5'),
        (None, None, None)
    )
    @ddt.unpack
    @mock.patch('ecommerce.extensions.api.serializers.sum_user_discounts_for_offer')
    def test_serialize_remaining_balance_for_user(
        self,
        max_user_discount,
        existing_user_spend,
        expected_remaining_balance_for_user,
        mock_sum_user_discounts_for_offer
    ):
        mock_sum_user_discounts_for_offer.return_value = existing_user_spend
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
        assert data['remaining_balance_for_user'] == expected_remaining_balance_for_user

    @ddt.data(
        (5250, '5250'),
        (None, None)
    )
    @ddt.unpack
    @mock.patch('ecommerce.extensions.api.serializers.calculate_remaining_offer_balance')
    def test_serialize_remaining_balance(
        self,
        max_discount,
        expected_remaining_balance,
        mock_calculate_remaining_offer_balance
    ):
        mock_calculate_remaining_offer_balance.return_value = max_discount
        enterprise_customer_uuid = str(uuid4())
        condition = extended_factories.EnterpriseCustomerConditionFactory(
            enterprise_customer_uuid=enterprise_customer_uuid
        )
        enterprise_offer = extended_factories.EnterpriseOfferFactory.create(
            partner=self.partner,
            condition=condition,
        )
        serializer = EnterpriseLearnerOfferApiSerializer(
            data=enterprise_offer,
            context={
                'request': mock.MagicMock(user=UserFactory())
            }
        )
        data = serializer.to_representation(enterprise_offer)
        assert data['remaining_balance'] == expected_remaining_balance

    @ddt.data(
        (1000, 1000),
        (None, None)
    )
    @ddt.unpack
    def test_serialize_remaining_applications_for_user(
        self,
        max_user_applications,
        expected_remaining_applications_for_user,
    ):
        enterprise_customer_uuid = str(uuid4())
        condition = extended_factories.EnterpriseCustomerConditionFactory(
            enterprise_customer_uuid=enterprise_customer_uuid
        )
        enterprise_offer = extended_factories.EnterpriseOfferFactory.create(
            partner=self.partner,
            condition=condition,
            max_user_applications=max_user_applications,
        )
        serializer = EnterpriseLearnerOfferApiSerializer(
            data=enterprise_offer,
            context={
                'request': mock.MagicMock(user=UserFactory())
            }
        )
        data = serializer.to_representation(enterprise_offer)
        assert data['remaining_applications_for_user'] == expected_remaining_applications_for_user

    @ddt.data(
        (2, 2),
        (None, None)
    )
    @ddt.unpack
    def test_serialize_remaining_applications(
        self,
        max_global_applications,
        expected_remaining_applications,
    ):
        enterprise_customer_uuid = str(uuid4())
        condition = extended_factories.EnterpriseCustomerConditionFactory(
            enterprise_customer_uuid=enterprise_customer_uuid
        )
        enterprise_offer = extended_factories.EnterpriseOfferFactory.create(
            partner=self.partner,
            condition=condition,
            max_global_applications=max_global_applications,
        )
        serializer = EnterpriseLearnerOfferApiSerializer(
            data=enterprise_offer,
            context={
                'request': mock.MagicMock(user=UserFactory())
            }
        )
        data = serializer.to_representation(enterprise_offer)
        assert data['remaining_applications'] == expected_remaining_applications
