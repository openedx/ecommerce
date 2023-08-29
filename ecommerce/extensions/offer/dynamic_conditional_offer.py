"""
Dynamic conditional offers allow us to calculate discount percentages and whether a course and user are eligible
for a discount elsewhere, and pass it in. We pass this information through a jwt on the request.
"""
import crum
import waffle
from edx_django_utils.monitoring import set_custom_attribute
from edx_rest_framework_extensions.auth.jwt.decoder import configured_jwt_decode_handler
from oscar.core.loading import get_class, get_model

from ecommerce.extensions.offer.constants import DYNAMIC_DISCOUNT_FLAG
from ecommerce.extensions.offer.mixins import (
    BenefitWithoutRangeMixin,
    ConditionWithoutRangeMixin,
    PercentageBenefitMixin,
    SingleItemConsumptionConditionMixin
)

Condition = get_model('offer', 'Condition')
PercentageDiscountBenefit = get_model('offer', 'PercentageDiscountBenefit')
ZERO_DISCOUNT = get_class('offer.results', 'ZERO_DISCOUNT')


def get_decoded_jwt_discount_from_request():
    request = crum.get_current_request()

    # We use a get request for display on the basket page,
    # and we use a post request for submitting  payment.
    if request.method == 'GET':
        discount_jwt = request.GET.get('discount_jwt')
    else:
        discount_jwt = request.POST.get('discount_jwt')
    if not discount_jwt:
        set_custom_attribute('ecom_discount_jwt', 'not-found')
        return None

    set_custom_attribute('ecom_discount_jwt', 'found')
    return configured_jwt_decode_handler(discount_jwt)


def get_percentage_from_request():
    decoded_jwt_discount = get_decoded_jwt_discount_from_request()
    if decoded_jwt_discount:
        return decoded_jwt_discount.get('discount_percent')
    return None


class DynamicPercentageDiscountBenefit(BenefitWithoutRangeMixin, PercentageDiscountBenefit, PercentageBenefitMixin):
    """Dynamic Percentage Discount Benefit without an attached range."""

    class Meta:
        app_label = 'offers'
        proxy = True

    @property
    def name(self):
        return 'dynamic_discount_benefit'

    @property
    def benefit_class_value(self):
        return get_percentage_from_request()

    def apply(self, basket, condition, offer, discount_percent=None,  # pylint: disable=unused-argument
              max_total_discount=None):
        """
        Apply the dynamic discount percent using the jwt that was passed in through the request.
        We haven't plumbed the discount_percent all the way through, so we will get the discount
        percent from the request.
        """
        if not waffle.flag_is_active(crum.get_current_request(), DYNAMIC_DISCOUNT_FLAG):
            return ZERO_DISCOUNT
        percent = self.benefit_class_value
        if percent:
            application_result = super(DynamicPercentageDiscountBenefit, self).apply(
                basket,
                condition,
                offer,
                discount_percent=percent,
                max_total_discount=max_total_discount)
            return application_result
        return ZERO_DISCOUNT


class DynamicDiscountCondition(ConditionWithoutRangeMixin, SingleItemConsumptionConditionMixin, Condition):
    """Dynamic Percentage Discount Condition without an attached range. """
    class Meta:
        app_label = 'offers'
        proxy = True

    @property
    def name(self):
        return "dynamic_discount_condition"

    def is_satisfied(self, offer, basket):  # pylint: disable=unused-argument
        """
        Check if the user and course is eligible for the discount using the jwt that was passed in through the request.
        We haven't plumbed the condition all the way through, so we will get the discount condition from the request
        here.
        """
        if not waffle.flag_is_active(crum.get_current_request(), DYNAMIC_DISCOUNT_FLAG):
            return False

        if basket.num_items > 1:
            return False

        if not basket.lines.first().product.is_seat_product:
            return False

        decoded_jwt_discount = get_decoded_jwt_discount_from_request()
        if decoded_jwt_discount:
            return decoded_jwt_discount.get('discount_applicable')
        return False
