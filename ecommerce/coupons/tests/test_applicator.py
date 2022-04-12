

from uuid import uuid4

import ddt
from oscar.core.loading import get_model
from oscar.test import factories
from oscar.test.factories import BasketFactory

from ecommerce.coupons.applicator import Applicator
from ecommerce.extensions.test.factories import ConditionalOfferFactory, ConditionFactory
from ecommerce.tests.factories import UserFactory
from ecommerce.tests.testcases import TestCase

BasketAttribute = get_model('basket', 'BasketAttribute')
BasketAttributeType = get_model('basket', 'BasketAttributeType')
ConditionalOffer = get_model('offer', 'ConditionalOffer')

@ddt.ddt
class ApplicatorTests(TestCase):
    """ Tests for the custom Applicator. """

    def setUp(self):
        self.applicator = Applicator()
        self.basket = factories.create_basket(empty=True)
        self.user = UserFactory()

    @ddt.unpack
    def test_get_offers(self):
        """ Verify get_offers returns correct objects based on filter"""

        enterprise_uuid = uuid4()
        basket = BasketFactory()
        setattr(basket, 'enterprise_customer_uuid', enterprise_uuid)

        for _ in range(2):
            condition = ConditionFactory(
                program_uuid=None,
                enterprise_customer_uuid=enterprise_uuid
            )
            ConditionalOfferFactory(condition=condition)

        # Make some condition offers with a uuid other than ours
        for _ in range(4):
            condition = ConditionFactory(
                program_uuid=None,
                enterprise_customer_uuid=uuid4()
            )
            ConditionalOfferFactory(condition=condition)

        offers = self.applicator.get_offers(
            basket,
            self.user,
            enterprise_uuid
        )

        assert len(offers) == 2
