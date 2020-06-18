

import uuid

from django.core.management import call_command
from oscar.core.loading import get_model
from oscar.test import factories

from ecommerce.tests.testcases import TestCase

Condition = get_model('offer', 'Condition')
ConditionalOffer = get_model('offer', 'ConditionalOffer')


class RemoveDuplicateConditionTests(TestCase):
    """Tests for remove_duplicate_conditions management command."""
    enterprise_customer_uuid = uuid.uuid4()
    enterprise_customer_catalog_uuid = uuid.uuid4()

    def create_condition(
            self,
            enterprise_customer_uuid,
            enterprise_customer_catalog_uuid,
            create_conditional_offer=True
    ):
        condition = factories.ConditionFactory(
            type='Count',
            value=1.00,
            proxy_class='ecommerce.enterprise.conditions.AssignableEnterpriseCustomerCondition',
            enterprise_customer_name='dummy-enterprise-name',
            enterprise_customer_uuid=enterprise_customer_uuid,
            enterprise_customer_catalog_uuid=enterprise_customer_catalog_uuid,
        )
        if create_conditional_offer:
            factories.ConditionalOfferFactory(condition=condition)
        return condition

    def test_remove_duplicate_conditions(self):
        self.create_condition(
            self.enterprise_customer_uuid,
            self.enterprise_customer_catalog_uuid,
            create_conditional_offer=False
        )
        self.create_condition(
            self.enterprise_customer_uuid,
            self.enterprise_customer_catalog_uuid,
            create_conditional_offer=False
        )
        num_of_conditions = Condition.objects.all().count()
        call_command('remove_duplicate_conditions')

        # There were 2 identical conditions, but only one will exist after command.
        self.assertEqual(Condition.objects.all().count(), num_of_conditions - 1)

    def test_remove_duplicate_conditions_with_conditional_offers(self):
        condition1 = self.create_condition(self.enterprise_customer_uuid, self.enterprise_customer_catalog_uuid)
        condition2 = self.create_condition(self.enterprise_customer_uuid, self.enterprise_customer_catalog_uuid)
        condition3 = self.create_condition(self.enterprise_customer_uuid, self.enterprise_customer_catalog_uuid)

        # Each condition has its own conditional_offer.
        self.assertEqual(ConditionalOffer.objects.filter(condition=condition1).count(), 1)
        self.assertEqual(ConditionalOffer.objects.filter(condition=condition2).count(), 1)
        self.assertEqual(ConditionalOffer.objects.filter(condition=condition3).count(), 1)

        num_of_conditions = Condition.objects.all().count()
        call_command('remove_duplicate_conditions')

        # There were 3 identical conditions, but only one will exist after command.
        self.assertEqual(Condition.objects.all().count(), num_of_conditions - 2)

        # All the conditional_offers will be associated with the remaining condition.
        remaining_condition = Condition.objects.get(enterprise_customer_uuid=self.enterprise_customer_uuid)
        self.assertEqual(ConditionalOffer.objects.filter(condition=remaining_condition).count(), 3)
