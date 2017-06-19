from decimal import Decimal

from django.db import models
from django.utils.translation import ugettext_lazy as _
from oscar.apps.offer import benefits, results

from ecommerce.enterprise.utils import is_user_linked_to_enterprise_customer


class EnterpriseCustomerUserPercentageBenefit(benefits.PercentageDiscountBenefit):
    """
    An offer benefit that gives a percentage discount for enterprise learners.

    This custom benefit covers use cases having to do with establishing relationships between an
    Open edX user/learner and an enterprise customer (ref: http://github.com/edx/edx-enterprise).
    """
    enterprise_customer_uuid = models.UUIDField()

    _description = _('%(value)s%% enterprise entitlement discount on %(range)s')

    class Meta(object):
        app_label = 'offer'
        verbose_name = _('Percentage enterprise entitlement discount benefit')
        verbose_name_plural = _('Percentage enterprise entitlement discount benefits')

    def apply(self, basket, condition, offer, discount_percent=None, max_total_discount=None):
        """
        Check that learner belongs to the enterprise and has consented to data sharing before applying discount.
        """
        if not is_user_linked_to_enterprise_customer(basket.site, self.enterprise_customer_uuid, basket.owner):
            return results.BasketDiscount(Decimal('0.0'))

        return super(EnterpriseCustomerUserPercentageBenefit, self).apply(
            basket=basket,
            condition=condition,
            offer=offer,
            discount_percent=discount_percent,
            max_total_discount=max_total_discount,
        )


class EnterpriseCustomerUserAbsoluteDiscountBenefit(benefits.AbsoluteDiscountBenefit):
    """
    An offer benefit that gives a absolute discount for enterprise learners.

    This custom benefit covers use cases having to do with establishing relationships between an
    Open edX user/learner and an enterprise customer (ref: http://github.com/edx/edx-enterprise).
    """
    enterprise_customer_uuid = models.UUIDField()

    _description = _('%(value)s%% enterprise entitlement discount on %(range)s')

    class Meta(object):
        app_label = 'offer'
        verbose_name = _('Absolute enterprise entitlement discount benefit')
        verbose_name_plural = _('Absolute enterprise entitlement discount benefits')

    def apply(self, basket, condition, offer, discount_amount=None, max_total_discount=None):
        """
        Check that learner belongs to the enterprise and has consented to data sharing before applying discount.
        """
        if not is_user_linked_to_enterprise_customer(basket.site, self.enterprise_customer_uuid, basket.owner):
            return results.BasketDiscount(Decimal('0.0'))

        return super(EnterpriseCustomerUserAbsoluteDiscountBenefit, self).apply(
            basket=basket,
            condition=condition,
            offer=offer,
            discount_amount=discount_amount,
            max_total_discount=max_total_discount,
        )
