from __future__ import unicode_literals

import logging

from oscar.core.loading import get_model
from requests.exceptions import ConnectionError, Timeout
from slumber.exceptions import SlumberHttpBaseException

from ecommerce.enterprise.api import catalog_contains_course_runs, fetch_enterprise_learner_data
from ecommerce.extensions.basket.utils import ENTERPRISE_CATALOG_ATTRIBUTE_TYPE
from ecommerce.enterprise.constants import ENTERPRISE_OFFERS_SWITCH
from ecommerce.extensions.basket.utils import ENTERPRISE_CATALOG_ATTRIBUTE_TYPE
from ecommerce.extensions.offer.decorators import check_condition_applicability
from ecommerce.extensions.offer.mixins import ConditionWithoutRangeMixin, SingleItemConsumptionConditionMixin


BasketAttribute = get_model('basket', 'BasketAttribute')
BasketAttributeType = get_model('basket', 'BasketAttributeType')
Condition = get_model('offer', 'Condition')
logger = logging.getLogger(__name__)


class EnterpriseCustomerCondition(ConditionWithoutRangeMixin, SingleItemConsumptionConditionMixin, Condition):
    class Meta(object):
        app_label = 'enterprise'
        proxy = True

    @property
    def name(self):
        return "Basket contains a seat from {}'s catalog".format(self.enterprise_customer_name)

    @check_condition_applicability([ENTERPRISE_OFFERS_SWITCH])
    def is_satisfied(self, offer, basket):  # pylint: disable=unused-argument
        """
        Determines if a user is eligible for an enterprise customer offer
        based on their association with the enterprise customer.

        It also verifies the catalog `catalog` on the
        offer with the catalog on the basket when provided.

        Args:
            basket (Basket): Contains information about order line items, the current site,
                             and the user attempting to make the purchase.
        Returns:
            bool
        """
        if not basket.owner:
            # An anonymous user is never linked to any EnterpriseCustomer.
            return False

        try:
            learner_data = fetch_enterprise_learner_data(basket.site, basket.owner)['results'][0]
        except (ConnectionError, KeyError, SlumberHttpBaseException, Timeout):
            logger.exception(
                'Failed to retrieve enterprise learner data for site [%s] and user [%s].',
                basket.site.domain,
                basket.owner.username,
            )
            return False
        except IndexError:
            return False

        enterprise_customer = learner_data['enterprise_customer']
        if str(self.enterprise_customer_uuid) != enterprise_customer['uuid']:
            # Learner is not linked to the EnterpriseCustomer associated with this condition.
            return False

        course_run_ids = []
        for line in basket.all_lines():
            course = line.product.course
            if not course:
                # Basket contains products not related to a course_run.
                return False

            course_run_ids.append(course.id)

        # Verify that the current conditional offer is related to the provided
        # enterprise catalog
        catalog = self._get_enterprise_catalog_uuid_from_basket(basket)
        if catalog:
            if str(offer.condition.enterprise_customer_catalog_uuid) != catalog:
                return False

        if not catalog_contains_course_runs(basket.site, course_run_ids, self.enterprise_customer_uuid,
                                            enterprise_customer_catalog_uuid=self.enterprise_customer_catalog_uuid):
            # Basket contains course runs that do not exist in the EnterpriseCustomerCatalogs
            # associated with the EnterpriseCustomer.
            return False

        return True

    @staticmethod
    def _get_enterprise_catalog_uuid_from_basket(basket):
        """
        Helper method for fetching enterprise catalog UUID from basket.

        Arguments:
             basket (Basket): The provided basket can be either temporary (just
             for calculating discounts) or an actual one to buy a product.
        """
        # For temporary basket try to get `catalog` from request
        catalog = basket.strategy.request.GET.get(
            'catalog'
        ) if basket.strategy.request else None

        if not catalog:
            # For actual baskets get `catalog` from basket attribute
            enterprise_catalog_attribute, __ = BasketAttributeType.objects.get_or_create(
                name=ENTERPRISE_CATALOG_ATTRIBUTE_TYPE
            )
            enterprise_customer_catalog = BasketAttribute.objects.filter(
                basket=basket,
                attribute_type=enterprise_catalog_attribute,
            ).first()
            if enterprise_customer_catalog:
                catalog = enterprise_customer_catalog.value_text

        return catalog
