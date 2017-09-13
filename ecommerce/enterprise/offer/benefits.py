from django.utils.translation import ugettext_lazy as _
from oscar.apps.offer.benefits import AbsoluteDiscountBenefit, PercentageDiscountBenefit

from ecommerce.extensions.offer.benefits import BenefitWithoutRangeMixin


class EnterprisePercentageDiscountBenefit(BenefitWithoutRangeMixin, PercentageDiscountBenefit):
    """ Enterprise-related PercentageDiscountBenefit without an attached range. """

    class Meta(object):
        app_label = 'enterprise'
        proxy = True

    @property
    def name(self):
        return _('{value}% enterprise discount').format(value=self.value)


class AbsoluteDiscountBenefitWithoutRange(BenefitWithoutRangeMixin, AbsoluteDiscountBenefit):
    """ Enterprise-related AbsoluteDiscountBenefit without an attached range. """

    class Meta(object):
        app_label = 'enterprise'
        proxy = True

    @property
    def name(self):
        return _('{value} fixed-price enterprise discount').format(value=self.value)
