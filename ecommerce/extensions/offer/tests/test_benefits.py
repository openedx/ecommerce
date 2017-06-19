from decimal import Decimal

import httpretty
import mock
from oscar.test import factories
from oscar.test.basket import add_product, add_products
from oscar.test.factories import BasketFactory, RangeFactory

from ecommerce.enterprise.tests.mixins import EnterpriseServiceMockMixin
from ecommerce.extensions.offer import models
from ecommerce.extensions.test.factories import (
    EnterpriseCustomerUserAbsoluteDiscountBenefitFactory,
    EnterpriseCustomerUserPercentageBenefitFactory
)
from ecommerce.tests.mixins import EnterpriseMixin


@httpretty.activate
class TestAPercentageDiscountAppliedWithConsentCondition(EnterpriseMixin, EnterpriseServiceMockMixin):
    """
    Tests for enterprise entitlement discount with data sharing consent conditions applied.
    """
    def setUp(self):
        """
        Common setup operations for each test case.
        """
        super(TestAPercentageDiscountAppliedWithConsentCondition, self).setUp()

        self.range = RangeFactory(includes_all_products=True)
        self.user = self.create_user(is_staff=True)
        self.client.login(username=self.user.username, password=self.password)

        self.condition = models.DataSharingConsentCondition(range=self.range)
        self.benefit = EnterpriseCustomerUserPercentageBenefitFactory(range=self.range)
        self.offer = mock.Mock()
        self.basket = BasketFactory(owner=self.user, site=self.site)

    def test_applies_correctly_to_empty_basket(self):
        """
        Test that benefits work correctly for empty basket.
        """
        self.mock_access_token_response()
        self.mock_enterprise_learner_api(
            learner_id=self.user.id,
            enterprise_customer_uuid=str(self.benefit.enterprise_customer_uuid),
        )

        result = self.benefit.apply(self.basket, self.condition, self.offer)
        self.assertEqual(Decimal('0.00'), result.discount)
        self.assertEqual(0, self.basket.num_items_with_discount)
        self.assertEqual(0, self.basket.num_items_without_discount)

    def test_applies_correctly_to_basket_with_no_discountable_products(self):
        """
        Test that benefits work correctly for basket with non-discountable items.
        """
        self.mock_access_token_response()
        self.mock_enterprise_learner_api(
            learner_id=self.user.id,
            enterprise_customer_uuid=str(self.benefit.enterprise_customer_uuid),
        )

        product = factories.create_product(is_discountable=False)
        add_product(self.basket, Decimal('12.00'), 2, product=product)
        result = self.benefit.apply(self.basket, self.condition, self.offer)
        self.assertEqual(Decimal('0.00'), result.discount)
        self.assertEqual(0, self.basket.num_items_with_discount)
        self.assertEqual(2, self.basket.num_items_without_discount)

    def test_applies_correctly_to_basket_with_non_enterprise_learner(self):
        """
        Test that benefits are not applied learners that do not belong to any enterprise learners.
        """
        with mock.patch(
            "ecommerce.extensions.offer.benefits.is_user_linked_to_enterprise_customer", return_value=False,
        ):
            product = factories.create_product(is_discountable=False)
            add_product(self.basket, Decimal('12.00'), 2, product=product)
            result = self.benefit.apply(self.basket, self.condition, self.offer)
            self.assertEqual(Decimal('0.00'), result.discount)
            self.assertEqual(0, self.basket.num_items_with_discount)
            self.assertEqual(2, self.basket.num_items_without_discount)

    def test_applies_correctly_to_basket_which_matches_condition(self):
        """
        Test that benefits is applied correctly to basket items.
        """
        self.mock_access_token_response()
        self.mock_enterprise_learner_api(
            learner_id=self.user.id,
            enterprise_customer_uuid=str(self.benefit.enterprise_customer_uuid),
        )

        add_product(self.basket, Decimal('12.00'), 2)
        result = self.benefit.apply(self.basket, self.condition, self.offer)
        self.assertEqual(2 * Decimal('12.00') * Decimal('0.1'), result.discount)
        self.assertEqual(2, self.basket.num_items_with_discount)
        self.assertEqual(0, self.basket.num_items_without_discount)


@httpretty.activate
class TestAnAbsoluteDiscountAppliedWithConsentCondition(EnterpriseMixin, EnterpriseServiceMockMixin):
    """
    Tests for enterprise entitlement discount with data sharing consent conditions applied.
    """

    def setUp(self):
        """
        Common setup operations for each test case.
        """
        super(TestAnAbsoluteDiscountAppliedWithConsentCondition, self).setUp()

        self.range = models.Range.objects.create(
            name="All products", includes_all_products=True,
        )
        self.user = self.create_user(is_staff=True)
        self.client.login(username=self.user.username, password=self.password)
        self.condition = models.DataSharingConsentCondition(range=self.range)
        self.benefit = EnterpriseCustomerUserAbsoluteDiscountBenefitFactory(range=self.range)
        self.offer = mock.Mock()
        self.basket = BasketFactory(owner=self.user, site=self.site)

    def test_applies_correctly_to_empty_basket(self):
        """
        Test that benefits work correctly empty basket.
        """
        self.mock_access_token_response()
        self.mock_enterprise_learner_api(
            learner_id=self.user.id,
            enterprise_customer_uuid=str(self.benefit.enterprise_customer_uuid),
        )
        result = self.benefit.apply(self.basket, self.condition, self.offer)
        self.assertEqual(Decimal('0.00'), result.discount)
        self.assertEqual(0, self.basket.num_items_with_discount)
        self.assertEqual(0, self.basket.num_items_without_discount)

    def test_applies_correctly_to_basket_with_no_discountable_products(self):
        """
        Test that benefits work correctly for basket with non-discountable items.
        """
        self.mock_access_token_response()
        self.mock_enterprise_learner_api(
            learner_id=self.user.id,
            enterprise_customer_uuid=str(self.benefit.enterprise_customer_uuid),
        )

        product = factories.create_product(is_discountable=False)
        add_product(self.basket, Decimal('12.00'), 2, product=product)

        result = self.benefit.apply(self.basket, self.condition, self.offer)
        self.assertEqual(Decimal('0.00'), result.discount)
        self.assertEqual(0, self.basket.num_items_with_discount)
        self.assertEqual(2, self.basket.num_items_without_discount)

    def test_applies_correctly_to_basket_with_non_enterprise_learner(self):
        """
        Test that benefits are not applied learners that do not belong to any enterprise learners.
        """
        with mock.patch(
            "ecommerce.extensions.offer.benefits.is_user_linked_to_enterprise_customer", return_value=False,
        ):
            add_products(self.basket, [(Decimal('10.00'), 1)])
            result = self.benefit.apply(self.basket, self.condition, self.offer)

            self.assertEqual(Decimal('0.00'), result.discount)
            self.assertEqual(0, self.basket.num_items_with_discount)
            self.assertEqual(1, self.basket.num_items_without_discount)

    def test_applies_correctly_to_single_item_basket_which_matches_condition(self):
        """
        Test that benefit applies correctly to single item baskets.
        """
        self.mock_access_token_response()
        self.mock_enterprise_learner_api(
            learner_id=self.user.id,
            enterprise_customer_uuid=str(self.benefit.enterprise_customer_uuid),
        )
        add_products(self.basket, [(Decimal('10.00'), 1)])
        result = self.benefit.apply(self.basket, self.condition, self.offer)
        self.assertEqual(Decimal('10.00'), result.discount)
        self.assertEqual(1, self.basket.num_items_with_discount)
        self.assertEqual(0, self.basket.num_items_without_discount)

    def test_applies_correctly_to_multi_item_basket_which_matches_condition(self):
        """
        Test that benefit applies correctly to multi item baskets.
        """
        self.mock_access_token_response()
        self.mock_enterprise_learner_api(
            learner_id=self.user.id,
            enterprise_customer_uuid=str(self.benefit.enterprise_customer_uuid),
        )
        add_products(self.basket, [(Decimal('5.00'), 2)])
        result = self.benefit.apply(self.basket, self.condition, self.offer)
        self.assertEqual(Decimal('10.00'), result.discount)
        self.assertEqual(2, self.basket.num_items_with_discount)
        self.assertEqual(0, self.basket.num_items_without_discount)
