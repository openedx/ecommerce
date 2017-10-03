from django.utils.translation import ugettext_lazy as _
from oscar.core.loading import get_model

from ecommerce.enterprise.benefits import EnterpriseAbsoluteDiscountBenefit, EnterprisePercentageDiscountBenefit

Benefit = get_model('offer', 'Benefit')

BENEFIT_MAP = {
    Benefit.FIXED: EnterpriseAbsoluteDiscountBenefit,
    Benefit.PERCENTAGE: EnterprisePercentageDiscountBenefit,
}
BENEFIT_TYPE_CHOICES = (
    (Benefit.PERCENTAGE, _('Percentage')),
    (Benefit.FIXED, _('Absolute')),
)

# Waffle switch used to enable/disable Enterprise offers.
ENTERPRISE_OFFERS_SWITCH = 'enable_enterprise_offers'
