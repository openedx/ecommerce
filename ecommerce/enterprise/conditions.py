from __future__ import unicode_literals

import logging
from uuid import UUID

import waffle
from oscar.core.loading import get_model
from requests.exceptions import ConnectionError, Timeout
from slumber.exceptions import SlumberHttpBaseException

from ecommerce.enterprise.api import catalog_contains_course_runs, fetch_enterprise_learner_data
from ecommerce.enterprise.constants import ENTERPRISE_OFFERS_FOR_COUPONS_SWITCH, ENTERPRISE_OFFERS_SWITCH
from ecommerce.extensions.basket.utils import ENTERPRISE_CATALOG_ATTRIBUTE_TYPE
from ecommerce.extensions.offer.decorators import check_condition_applicability
from ecommerce.extensions.offer.mixins import ConditionWithoutRangeMixin, SingleItemConsumptionConditionMixin

BasketAttribute = get_model('basket', 'BasketAttribute')
BasketAttributeType = get_model('basket', 'BasketAttributeType')
Condition = get_model('offer', 'Condition')
ConditionalOffer = get_model('offer', 'ConditionalOffer')
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

        It also filter out the offer if the `enterprise_customer_catalog_uuid`
        value set on the offer condition does not match with the basket catalog
        value when explicitly provided by the enterprise learner.

        Note: Currently there is no mechanism to prioritize or apply multiple
        offers that may apply as opposed to disqualifying offers if the
        catalog doesn't explicitly match.

        Arguments:
            basket (Basket): Contains information about order line items, the current site,
                             and the user attempting to make the purchase.
        Returns:
            bool
        """
        if not basket.owner:
            # An anonymous user is never linked to any EnterpriseCustomer.
            return False

        if (offer.offer_type == ConditionalOffer.VOUCHER and
                not waffle.switch_is_active(ENTERPRISE_OFFERS_FOR_COUPONS_SWITCH)):
            logger.info('Skipping Voucher type enterprise conditional offer until we are ready to support it.')
            return False

        learner_data = {}
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
            if offer.offer_type == ConditionalOffer.SITE:
                logger.warning(
                    'Unable to apply enterprise site offer %s because no learner data was returned for user %s',
                    offer.id,
                    basket.owner)
                return False

        if (learner_data and 'enterprise_customer' in learner_data and
                str(self.enterprise_customer_uuid) != learner_data['enterprise_customer']['uuid']):
            # Learner is not linked to the EnterpriseCustomer associated with this condition.
            logger.warning('Unable to apply enterprise offer %s because Learner\'s enterprise (%s)'
                           'does not match this conditions\'s enterprise (%s).',
                           offer.id,
                           learner_data['enterprise_customer']['uuid'],
                           str(self.enterprise_customer_uuid))
            return False

        course_run_ids = []
        for line in basket.all_lines():
            course = line.product.course
            if not course:
                # Basket contains products not related to a course_run.
                logger.warning('Unable to apply enterprise offer %s because '
                               'the Basket (#%s) contains a product (#%s) not related to a course_run.',
                               offer.id, basket.id, line.product.id)
                return False

            course_run_ids.append(course.id)

        # Verify that the current conditional offer is related to the provided
        # enterprise catalog, this will also filter out offers which don't
        # have `enterprise_customer_catalog_uuid` value set on the condition.
        catalog = self._get_enterprise_catalog_uuid_from_basket(basket)
        if catalog:
            if offer.condition.enterprise_customer_catalog_uuid != catalog:
                logger.warning('Unable to apply enterprise offer %s because '
                               'Enterprise catalog id on the basket (%s) '
                               'does not match the catalog for this condition (%s).',
                               offer.id, catalog, offer.condition.enterprise_customer_catalog_uuid)
                return False

        if not catalog_contains_course_runs(basket.site, course_run_ids, self.enterprise_customer_uuid,
                                            enterprise_customer_catalog_uuid=self.enterprise_customer_catalog_uuid):
            # Basket contains course runs that do not exist in the EnterpriseCustomerCatalogs
            # associated with the EnterpriseCustomer.
            logger.warning('Unable to apply enterprise offer %s because '
                           'Enterprise catalog (%s) does not contain the course(s) (%s) in this basket.',
                           offer.id, self.enterprise_customer_catalog_uuid, ','.join(course_run_ids))
            return False

        return True

    @staticmethod
    def _get_enterprise_catalog_uuid_from_basket(basket):
        """
        Helper method for fetching valid enterprise catalog UUID from basket.

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

        # Return only valid UUID
        try:
            catalog = UUID(catalog) if catalog else None
        except ValueError:
            catalog = None

        return catalog
