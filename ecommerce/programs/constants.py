

from django.utils.translation import ugettext_lazy as _
from oscar.core.loading import get_model

from ecommerce.programs.benefits import AbsoluteDiscountBenefitWithoutRange, PercentageDiscountBenefitWithoutRange

Benefit = get_model('offer', 'Benefit')

BENEFIT_MAP = {
    Benefit.FIXED: AbsoluteDiscountBenefitWithoutRange,
    Benefit.PERCENTAGE: PercentageDiscountBenefitWithoutRange,
}
BENEFIT_TYPE_CHOICES = (
    (Benefit.PERCENTAGE, _('Percentage')),
    (Benefit.FIXED, _('Absolute')),
)
