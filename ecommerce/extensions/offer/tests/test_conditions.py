from decimal import Decimal

import ddt
import httpretty
import mock
from oscar.test import factories
from oscar.test.factories import BasketFactory, RangeFactory

from ecommerce.enterprise.tests.mixins import EnterpriseServiceMockMixin
from ecommerce.extensions.offer import models


@ddt.ddt
@httpretty.activate
class DataSharingConsentConditionTests(EnterpriseServiceMockMixin):

    def setUp(self):
        super(DataSharingConsentConditionTests, self).setUp()

        self.user = self.create_user(is_staff=True)
        self.range = RangeFactory(includes_all_products=True)
        self.basket = BasketFactory(owner=self.user, site=self.site)
        self.condition = models.DataSharingConsentCondition(range=self.range)
        self.product = factories.create_product(price=Decimal('5.00'))

    def test_name(self):
        """
        Test the name of the data sharing consent condition.
        """
        self.assertEqual(
            'Enterprise learner has consented to data sharing',
            self.condition.name,
        )
        self.assertEqual(
            'Enterprise learner has consented to data sharing',
            self.condition.description,
        )

    def test_description(self):
        """
        Test the description of the data sharing consent condition.
        """
        self.assertEqual(
            'Enterprise learner has consented to data sharing',
            self.condition.name,
        )
        self.assertEqual(
            'Enterprise learner has consented to data sharing',
            self.condition.description,
        )

    def test_condition_fails_for_none_enterprise_learner(self):
        """
        Test that condition fails if learner does not belong to any enterprise.
        """
        self.basket.add_product(product=self.product)

        with mock.patch(
            "ecommerce.extensions.offer.conditions.enterprise_utils.get_enterprise_learner", return_value=None,
        ):
            self.assertFalse(self.condition.is_satisfied(None, self.basket))

    def test_condition_fails_for_no_basket_owner(self):
        """
        Test that condition fails if basket does not have any owner.
        """
        self.assertFalse(self.condition.is_satisfied(None, BasketFactory()))

    @ddt.data(
        (True, False, False),
        (True, True, True),
        (False, True, True),
        (False, False, True),
    )
    @ddt.unpack
    def test_condition_for_consent(self, is_consent_enabled, is_consent_provided, expected_condition_result):
        """
        Test consent related scenarios for enterprise customer and enterprise learner.
        """
        self.basket.add_product(product=self.product)

        # Mock API so that enterprise learner requires data sharing consent.
        # And learner has not provided data sharing consent.
        self.mock_access_token_response()
        self.mock_enterprise_learner_api(
            learner_id=self.user.id,
            consent_enabled=is_consent_enabled,
            consent_provided=is_consent_provided,
        )

        self.assertEqual(
            expected_condition_result,
            self.condition.is_satisfied(None, self.basket),
        )
