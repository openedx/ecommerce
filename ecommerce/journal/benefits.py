"""
Defines Types of Benefits for Journal Bundle Conditional Offers
"""
from django.utils.translation import ugettext_lazy as _
from oscar.apps.offer.benefits import AbsoluteDiscountBenefit, PercentageDiscountBenefit
from oscar.core.loading import get_model

from ecommerce.extensions.offer.mixins import AbsoluteBenefitMixin, BenefitWithoutRangeMixin, PercentageBenefitMixin

Benefit = get_model('offer', 'Benefit')


class JournalBundlePercentageDiscountBenefit(BenefitWithoutRangeMixin, PercentageBenefitMixin,
                                             PercentageDiscountBenefit):
    """ Journal Bundle related PercentageDiscountBenefit without attached range"""

    class Meta(object):
        app_label = 'journal'
        proxy = True

    @property
    def name(self):
        return _('%d%% journal bundle discount') % self.value


class JournalBundleAbsoluteDiscountBenefit(BenefitWithoutRangeMixin, AbsoluteBenefitMixin, AbsoluteDiscountBenefit):
    """ Journal Bundle related AbsoluteDiscountBenefit without attached range"""

    class Meta(object):
        app_label = 'journal'
        proxy = True

    @property
    def name(self):
        return _('%d fixed-price journal bundle discount') % self.value
