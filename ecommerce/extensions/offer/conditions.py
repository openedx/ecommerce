import logging
from django.utils.translation import ugettext as _
from oscar.core.loading import get_model
from requests.exceptions import ConnectionError, Timeout
from slumber.exceptions import SlumberBaseException
from ecommerce.enterprise import utils as enterprise_utils


Condition = get_model('offer', 'Condition')
logger = logging.getLogger(__name__)


class DataSharingConsentCondition(Condition):
    """
    An offer condition dependent on the data sharing consent of
    enterprise learner.
    """
    name = _('Enterprise learner has consented to data sharing')

    @property
    def description(self):
        return self.name

    class Meta(object):
        proxy = True

    def is_satisfied(self, offer, basket):  # pylint: disable=unused-argument
        """
        Determines whether enterprise learner is eligible for entitlements.
        """
        # There must be a basket owner for enterprise entitlements
        if not basket.owner:
            return False

        try:
            enterprise_learner = enterprise_utils.get_enterprise_learner(basket.site, basket.owner)
        except (ConnectionError, SlumberBaseException, Timeout):
            logger.exception('Failed to retrieve learner data for "%s"', basket.owner.username)
            return False

        # If there is no enterprise learner for the current user,
        # then user is not entitled to enterprise discounts.
        if not enterprise_learner:
            return False

        # If enterprise customer requires data sharing consent but enterprise learner has not
        # consented then return False.
        if enterprise_utils.enterprise_customer_needs_consent(enterprise_learner['enterprise_customer']) and \
                not enterprise_utils.enterprise_customer_user_consent_provided(enterprise_learner):
            return False

        return True
