import waffle
import crum

from ecommerce.extensions.offer.mixins import BenefitWithoutRangeMixin, PercentageBenefitMixin, ConditionWithoutRangeMixin, SingleItemConsumptionConditionMixin
from oscar.core.loading import get_model
from ecommerce.extensions.api.handlers import jwt_decode_handler

PercentageDiscountBenefit = get_model('offer', 'PercentageDiscountBenefit')
Condition = get_model('offer', 'Condition')


def _get_decoded_jwt_discount_from_request():
    request = crum.get_current_request()
    if not waffle.flag_is_active(request, 'offer.dynamic_discount'):
        return None

    if request.method == 'GET':
        discount_jwt = request.GET.get('discount_jwt')
    else:
        discount_jwt = request.POST.get('discount_jwt')
    if not discount_jwt:
        return None
    import pdb; pdb.set_trace()
    return jwt_decode_handler(discount_jwt)


class DynamicPercentageDiscountBenefit(BenefitWithoutRangeMixin, PercentageDiscountBenefit):
    """ Dynamic PercentageDiscountBenefit without an attached range. """

    class Meta(object):
        app_label = 'offers'
        proxy = True

    @property
    def name(self):
        # NOTE: We are not using str.format() because gettext incorrectly parses the string,
        # resulting in translation compilation errors.
        return ('%d%% dynamic discount') % self.value

    def apply(self, basket, condition, offer, discount_percent=None,
              max_total_discount=None):
        decoded_jwt_discount = _get_decoded_jwt_discount_from_request()
        if decoded_jwt_discount and decoded_jwt_discount.get('discount_percent'):
            return super(DynamicPercentageDiscountBenefit, self).apply(
                basket, 
                condition, 
                offer, 
                discount_percent=decoded_jwt_discount['discount_percent'],
                max_total_discount=max_total_discount)
        # What do I do here in the else?
        return None


class DynamicCustomerCondition(ConditionWithoutRangeMixin, SingleItemConsumptionConditionMixin, Condition):
    class Meta(object):
        app_label = 'offers'
        proxy = True

    @property
    def name(self):
        return "First time purchaser condition"

    def is_satisfied(self, offer, basket):  # pylint: disable=unused-argument
        decoded_jwt_discount = _get_decoded_jwt_discount_from_request()
        if decoded_jwt_discount:
            return decoded_jwt_discount.get('discount_applicable')
        return False
