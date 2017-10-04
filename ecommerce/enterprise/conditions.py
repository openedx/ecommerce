from __future__ import unicode_literals

import logging

from oscar.core.loading import get_model
from requests.exceptions import ConnectionError, Timeout
from slumber.exceptions import SlumberHttpBaseException

from ecommerce.enterprise.api import catalog_contains_course_runs, fetch_enterprise_learner_data
from ecommerce.enterprise.constants import ENTERPRISE_OFFERS_SWITCH
from ecommerce.extensions.offer.decorators import check_condition_applicability
from ecommerce.extensions.offer.mixins import ConditionWithoutRangeMixin, SingleItemConsumptionConditionMixin

Condition = get_model('offer', 'Condition')
logger = logging.getLogger(__name__)


class EnterpriseCustomerCondition(ConditionWithoutRangeMixin, SingleItemConsumptionConditionMixin, Condition):
    class Meta(object):
        app_label = 'enterprise'
        proxy = True

    @property
    def name(self):
        return "Basket contains a seat from {}'s catalog".format(self.enterprise_customer_name)

    def _get_course_runs_with_consent(self, data_sharing_consent_records):
        """
        Return the course run IDs for which the learner has consented to share data.

        Arguments:
            data_sharing_consent_records (list of dict): The learner's existing data sharing consent records.

        Returns:
            list of strings: The list of course run IDs for which the learner has given data sharing consent.
        """
        return [record['course_id'] for record in data_sharing_consent_records if record['consent_provided']]

    @check_condition_applicability([ENTERPRISE_OFFERS_SWITCH])
    def is_satisfied(self, offer, basket):  # pylint: disable=unused-argument
        """
        Determines if a user is eligible for an enterprise customer offer
        based on their association with the enterprise customer and whether
        or not they have consented to sharing data with the enterprise customer.

        Args:
            basket (Basket): Contains information about order line items, the current site,
                             and the user attempting to make the purchase.
        Returns:
            bool
        """
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
            # Learner is not linked to any EnterpriseCustomer.
            return False

        enterprise_customer = learner_data['enterprise_customer']
        if str(self.enterprise_customer_uuid) != enterprise_customer['uuid']:
            # Learner is not linked to the EnterpriseCustomer associated with this condition.
            return False

        course_runs_with_consent = self._get_course_runs_with_consent(learner_data['data_sharing_consent_records'])
        course_run_ids = []
        for line in basket.all_lines():
            course = line.product.course
            if not course:
                # Basket contains products not related to a course_run.
                return False

            if enterprise_customer['enable_data_sharing_consent'] and course.id not in course_runs_with_consent:
                # Basket contains course_runs for which the learner has not given consent to share data.
                return False

            course_run_ids.append(course.id)

        if not catalog_contains_course_runs(basket.site, course_run_ids, self.enterprise_customer_uuid,
                                            enterprise_customer_catalog_uuid=self.enterprise_customer_catalog_uuid):
            # Basket contains course runs that do not exist in the EnterpriseCustomerCatalogs
            # associated with the EnterpriseCustomer.
            return False

        return True
