from django.utils.translation import ugettext_lazy as _
from oscar.apps.offer.benefits import AbsoluteDiscountBenefit, PercentageDiscountBenefit
from oscar.core.loading import get_model

from ecommerce.extensions.offer.mixins import AbsoluteBenefitMixin, BenefitWithoutRangeMixin, PercentageBenefitMixin

Benefit = get_model('offer', 'Benefit')


class EnterprisePercentageDiscountBenefit(BenefitWithoutRangeMixin, PercentageBenefitMixin, PercentageDiscountBenefit):
    """ Enterprise-related PercentageDiscountBenefit without an attached range. """

    class Meta(object):
        app_label = 'enterprise'
        proxy = True

    @property
    def name(self):
        # NOTE: We are not using str.format() because gettext incorrectly parses the string,
        # resulting in translation compilation errors.
        return _('%d%% enterprise discount') % self.value


class EnterpriseAbsoluteDiscountBenefit(BenefitWithoutRangeMixin, AbsoluteBenefitMixin, AbsoluteDiscountBenefit):
    """ Enterprise-related AbsoluteDiscountBenefit without an attached range. """

    class Meta(object):
        app_label = 'enterprise'
        proxy = True

    @property
    def name(self):
        return _('{value} fixed-price enterprise discount').format(value=self.value)
