from django.utils.translation import ugettext_lazy as _
from oscar.core.loading import get_model

from ecommerce.digital_books.benefits import DigitalBookAbsoluteDiscountBenefit, DigitalBookPercentageDiscountBenefit

Benefit = get_model('offer', 'Benefit')

BENEFIT_MAP = {
    Benefit.FIXED: DigitalBookAbsoluteDiscountBenefit,
    Benefit.PERCENTAGE: DigitalBookPercentageDiscountBenefit,
}

BENEFIT_TYPE_CHOICES = (
    (Benefit.PERCENTAGE, _('Percentage')),
    (Benefit.FIXED, _('Absolute')),
)