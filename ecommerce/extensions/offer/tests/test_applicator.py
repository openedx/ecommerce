

from uuid import uuid4

import ddt
import mock
from oscar.core.loading import get_model
from oscar.test import factories

from ecommerce.core.constants import SYSTEM_ENTERPRISE_LEARNER_ROLE
from ecommerce.extensions.offer.applicator import Applicator
from ecommerce.extensions.test.factories import ConditionalOfferFactory, ConditionFactory, ProgramOfferFactory
from ecommerce.tests.factories import UserFactory
from ecommerce.tests.testcases import TestCase

BasketAttribute = get_model('basket', 'BasketAttribute')
BasketAttributeType = get_model('basket', 'BasketAttributeType')
ConditionalOffer = get_model('offer', 'ConditionalOffer')

BUNDLE = 'bundle_identifier'
LOGGER_NAME = 'ecommerce.extensions.offer.applicator'


@ddt.ddt
class ApplicatorTests(TestCase):
    """ Tests for the custom Applicator. """

    def setUp(self):
        self.applicator = Applicator()
        self.basket = factories.create_basket(empty=True)
        self.user = UserFactory()

    def create_bundle_attribute(self, bundle_id):
        """ Helper to add a bundle attribute to a basket. """
        BasketAttribute.objects.create(
            basket=self.basket,
            attribute_type=BasketAttributeType.objects.get(name=BUNDLE),
            value_text=bundle_id,
        )

    def assert_correct_offers(self, expected_offers):
        """ Helper to verify applicator returns the expected offers. """
        # No need to pass a request to get_offers since we currently don't support session offers
        with mock.patch('ecommerce.enterprise.utils.get_decoded_jwt') as mock_get_jwt:
            mock_get_jwt.return_value = {
                'roles': ['{}:{}'.format(SYSTEM_ENTERPRISE_LEARNER_ROLE, uuid4())]
            }
            offers = self.applicator.get_offers(self.basket, self.user)  # pylint: disable=protected-access
        self.assertEqual(offers, expected_offers)

    def test_get_offers_with_bundle(self):
        """ Verify that only offers related to the bundle id are returned. """
        program_offers = [ProgramOfferFactory()]
        bundle_id = program_offers[0].condition.program_uuid
        self.create_bundle_attribute(bundle_id)

        ConditionalOfferFactory.create_batch(2)  # Unrelated offers that should not be returned

        self.applicator.get_site_offers = mock.Mock()
        self.assert_correct_offers(program_offers)
        self.assertFalse(self.applicator.get_site_offers.called)  # Verify there was no attempt to get all site offers

    def test_get_offers_without_bundle(self):
        """ Verify that all non bundle offers are returned if no bundle id is given. """
        offers_in_db = list(ConditionalOffer.active.filter(offer_type=ConditionalOffer.SITE))
        site_offers = ConditionalOfferFactory.create_batch(3) + offers_in_db
        ProgramOfferFactory()

        # Verify that program offer was not returned without bundle_id
        self.assert_correct_offers(site_offers)

    def test_get_site_offers(self):
        """ Verify get_site_offers returns correct objects based on filter"""
        existing_offers = list(ConditionalOffer.active.filter(offer_type=ConditionalOffer.SITE))

        uuid = uuid4()
        for _ in range(2):
            condition = ConditionFactory(
                program_uuid=None,
                enterprise_customer_uuid=uuid
            )
            ConditionalOfferFactory(condition=condition)
        for _ in range(3):
            condition = ConditionFactory(
                program_uuid=None,
                enterprise_customer_uuid=None
            )
            ConditionalOfferFactory(condition=condition)
        assert self.applicator.get_site_offers().count() == 3 + len(existing_offers)

    @ddt.data(
        (uuid4(), 2),
        (None, 0),
    )
    @ddt.unpack
    def test_get_enterprise_offers(self, enterprise_id, num_expected_offers):
        """ Verify get_enterprise_offers returns correct objects based on filter"""

        uuid = enterprise_id or uuid4()

        for _ in range(2):
            condition = ConditionFactory(
                program_uuid=None,
                enterprise_customer_uuid=uuid
            )
            ConditionalOfferFactory(condition=condition)
        for _ in range(3):
            condition = ConditionFactory(
                program_uuid=None,
                enterprise_customer_uuid=None
            )
            ConditionalOfferFactory(condition=condition)
        # Make some condition offers with a uuid other than ours
        for _ in range(4):
            condition = ConditionFactory(
                program_uuid=None,
                enterprise_customer_uuid=uuid4()
            )
            ConditionalOfferFactory(condition=condition)

        with mock.patch('ecommerce.extensions.offer.applicator.get_enterprise_id_for_user') as mock_ent_id:
            mock_ent_id.return_value = enterprise_id
            # pylint: disable=protected-access
            enterprise_offers = self.applicator._get_enterprise_offers(
                'some-site',
                self.user
            )

        if num_expected_offers == 0:
            assert not enterprise_offers
        else:
            assert enterprise_offers.count() == num_expected_offers
