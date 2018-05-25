from django.utils.translation import ugettext_lazy as _
from oscar.core.loading import get_model

from ecommerce.digital_books.benefits import DigitalBookAbsoluteDiscountBenefitWithoutRange, DigitalBookPercentageDiscountBenefitWithoutRange
Benefit = get_model('offer', 'Benefit')

BENEFIT_MAP = {
    Benefit.FIXED: DigitalBookAbsoluteDiscountBenefitWithoutRange,
    Benefit.PERCENTAGE: DigitalBookPercentageDiscountBenefitWithoutRange,
}

BENEFIT_TYPE_CHOICES = (
    (Benefit.PERCENTAGE, _('Percentage')),
    (Benefit.FIXED, _('Absolute')),
)