# TODO: Refactor this to consolidate it with `ecommerce.programs.constants`.
import six
from django.utils.translation import ugettext_lazy as _
from oscar.core.loading import get_model

from ecommerce.enterprise.offer.benefits import (
    AbsoluteDiscountBenefitWithoutRange,
    EnterprisePercentageDiscountBenefit
)
from ecommerce.programs.custom import class_path

Benefit = get_model('offer', 'Benefit')

BENEFIT_MAP = {
    Benefit.FIXED: AbsoluteDiscountBenefitWithoutRange,
    Benefit.PERCENTAGE: EnterprisePercentageDiscountBenefit,
}
BENEFIT_PROXY_CLASS_MAP = dict(
    (class_path(proxy_class), benefit_type) for benefit_type, proxy_class in six.iteritems(BENEFIT_MAP)
)
BENEFIT_TYPE_CHOICES = (
    (Benefit.PERCENTAGE, _('Percentage')),
    (Benefit.FIXED, _('Absolute')),
)
