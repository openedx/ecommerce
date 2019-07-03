import waffle
import crum

from ecommerce.extensions.offer.mixins import BenefitWithoutRangeMixin, PercentageBenefitMixin, ConditionWithoutRangeMixin, SingleItemConsumptionConditionMixin
from oscar.core.loading import get_model
from ecommerce.extensions.api.handlers import jwt_decode_handler
from ecommerce.extensions.offer.constants import DYNAMIC_DISCOUNT_FLAG

PercentageDiscountBenefit = get_model('offer', 'PercentageDiscountBenefit')
Condition = get_model('offer', 'Condition')


def get_decoded_jwt_discount_from_request():
    request = crum.get_current_request()
    if request.method == 'GET':
        discount_jwt = request.GET.get('discount_jwt')
    else:
        discount_jwt = request.POST.get('discount_jwt')
    if not discount_jwt:
        return None
    return jwt_decode_handler(discount_jwt)

def get_percentage_from_request():
    decoded_jwt_discount = get_decoded_jwt_discount_from_request()
    if decoded_jwt_discount:
        return decoded_jwt_discount.get('discount_percent')
    else:
        return None

class DynamicPercentageDiscountBenefit(BenefitWithoutRangeMixin, PercentageDiscountBenefit):
    """ Dynamic PercentageDiscountBenefit without an attached range. """

    class Meta(object):
        app_label = 'offers'
        proxy = True

    @property
    def name(self):
        return 'dynamic_discount_benefit'

    def apply(self, basket, condition, offer, discount_percent=None,
              max_total_discount=None):
        if not waffle.flag_is_active(crum.get_current_request(), DYNAMIC_DISCOUNT_FLAG):
            return None
        percent = get_percentage_from_request()
        if percent:
            application_result = super(DynamicPercentageDiscountBenefit, self).apply(
                basket, 
                condition, 
                offer, 
                discount_percent=percent,
                max_total_discount=max_total_discount)
            return application_result
        return None


class DynamicCustomerCondition(ConditionWithoutRangeMixin, SingleItemConsumptionConditionMixin, Condition):
    class Meta(object):
        app_label = 'offers'
        proxy = True

    @property
    def name(self):
        return "dynamic_discount_condition"

    def is_satisfied(self, offer, basket):  # pylint: disable=unused-argument
        if not waffle.flag_is_active(crum.get_current_request(), DYNAMIC_DISCOUNT_FLAG):
            return False
        decoded_jwt_discount = get_decoded_jwt_discount_from_request()
        if decoded_jwt_discount:
            return decoded_jwt_discount.get('discount_applicable')
        return False
