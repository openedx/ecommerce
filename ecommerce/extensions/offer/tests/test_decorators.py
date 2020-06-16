

from mock import patch
from oscar.test.factories import ConditionalOfferFactory, ConditionFactory
from waffle.models import Switch

from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.extensions.offer.decorators import check_condition_applicability
from ecommerce.extensions.test.factories import create_basket
from ecommerce.tests.factories import SiteConfigurationFactory, UserFactory
from ecommerce.tests.testcases import TestCase


class OfferDecoratorTests(DiscoveryTestMixin, TestCase):

    def setUp(self):
        super(OfferDecoratorTests, self).setUp()
        self.condition = ConditionFactory()
        self.offer = ConditionalOfferFactory(condition=self.condition, partner=self.partner)
        self.user = UserFactory()

    @patch('ecommerce.extensions.offer.models.Condition.is_satisfied')
    def test_check_condition_applicability(self, mock_is_satisfied):
        """
        Validate check_condition_applicability decorator returns True if it is applicable.
        """
        mock_is_satisfied.return_value = True
        mock_is_satisfied.__name__ = 'is_satisfied'
        basket = create_basket(self.user, self.site)

        self.assertTrue(
            check_condition_applicability()(self.condition.is_satisfied)(self.condition, self.offer, basket)
        )

    def test_check_condition_applicability_site_mismatch(self):
        """
        Validate check_condition_applicability decorator returns False if the offer site and basket site do not match.
        """
        basket = create_basket(self.user, SiteConfigurationFactory().site)

        self.assertFalse(
            check_condition_applicability()(self.condition.is_satisfied)(self.condition, self.offer, basket)
        )

    def test_check_condition_applicability_empty_basket(self):
        """
        Validate check_condition_applicability decorator returns False if the basket is empty.
        """
        basket = create_basket(self.user, self.site, empty=True)

        self.assertFalse(
            check_condition_applicability()(self.condition.is_satisfied)(self.condition, self.offer, basket)
        )

    def test_check_condition_applicability_free_basket(self):
        """
        Validate check_condition_applicability decorator returns False if the basket is free.
        """
        basket = create_basket(self.user, self.site, price='0.00')

        self.assertFalse(
            check_condition_applicability()(self.condition.is_satisfied)(self.condition, self.offer, basket)
        )

    @patch('ecommerce.extensions.offer.models.Condition.is_satisfied')
    def test_check_condition_applicability_switch_active(self, mock_is_satisfied):
        """
        Validate check_condition_applicability decorator returns False if the specified switch is active.
        """
        mock_is_satisfied.return_value = True
        mock_is_satisfied.__name__ = 'is_satisfied'
        basket = create_basket(self.user, self.site)
        switch = 'fake_switch'
        Switch.objects.update_or_create(name=switch, defaults={'active': True})

        self.assertTrue(
            check_condition_applicability([switch])(self.condition.is_satisfied)(self.condition, self.offer, basket)
        )

    def test_check_condition_applicability_switch_inactive(self):
        """
        Validate check_condition_applicability decorator returns False if the specified switch is inactive.
        """
        basket = create_basket(self.user, self.site)
        switch = 'fake_switch'
        Switch.objects.update_or_create(name=switch, defaults={'active': False})

        self.assertFalse(
            check_condition_applicability([switch])(self.condition.is_satisfied)(self.condition, self.offer, basket)
        )
