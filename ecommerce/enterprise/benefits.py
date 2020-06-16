

from django.utils.translation import ugettext_lazy as _
from oscar.core.loading import get_model

from ecommerce.extensions.offer.mixins import AbsoluteBenefitMixin, BenefitWithoutRangeMixin, PercentageBenefitMixin

Benefit = get_model('offer', 'Benefit')
AbsoluteDiscountBenefit = get_model('offer', 'AbsoluteDiscountBenefit')
PercentageDiscountBenefit = get_model('offer', 'PercentageDiscountBenefit')


class EnterprisePercentageDiscountBenefit(BenefitWithoutRangeMixin, PercentageBenefitMixin, PercentageDiscountBenefit):
    """ Enterprise-related PercentageDiscountBenefit without an attached range. """

    class Meta:
        app_label = 'enterprise'
        proxy = True

    @property
    def name(self):
        # NOTE: We are not using str.format() because gettext incorrectly parses the string,
        # resulting in translation compilation errors.
        return _('%d%% enterprise discount') % self.value


class EnterpriseAbsoluteDiscountBenefit(BenefitWithoutRangeMixin, AbsoluteBenefitMixin, AbsoluteDiscountBenefit):
    """ Enterprise-related AbsoluteDiscountBenefit without an attached range. """

    class Meta:
        app_label = 'enterprise'
        proxy = True

    @property
    def name(self):
        return _('{value} fixed-price enterprise discount').format(value=self.value)


# constants related to enterprise benefits
BENEFIT_MAP = {
    Benefit.FIXED: EnterpriseAbsoluteDiscountBenefit,
    Benefit.PERCENTAGE: EnterprisePercentageDiscountBenefit,
}
BENEFIT_TYPE_CHOICES = (
    (Benefit.PERCENTAGE, _('Percentage')),
    (Benefit.FIXED, _('Absolute')),
)
