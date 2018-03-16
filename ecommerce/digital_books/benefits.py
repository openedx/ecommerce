from django.utils.translation import ugettext_lazy as _
from oscar.apps.offer.benefits import AbsoluteDiscountBenefit, PercentageDiscountBenefit
from oscar.core.loading import get_model

from ecommerce.extensions.offer.mixins import AbsoluteBenefitMixin, BenefitWithoutRangeMixin, PercentageBenefitMixin

Benefit = get_model('offer', 'Benefit')


# TODO: rename
class DigitalBookPercentageDiscountBenefit(BenefitWithoutRangeMixin, PercentageBenefitMixin, PercentageDiscountBenefit):
    """ Digital Book related Percentage Discount Benefit without an attached range. """

    class Meta(object):
        app_label = 'digital_books'
        proxy = True

    @property
    def name(self):
        return _('{value}% digital book discount').format(value=self.value)


class DigitalBookAbsoluteDiscountBenefit(BenefitWithoutRangeMixin, AbsoluteBenefitMixin, AbsoluteDiscountBenefit):
    """ Digital Book related Absolute Discount Benefit without an attached range. """

    class Meta(object):
        app_label = 'digital_books'
        proxy = True

    @property
    def name(self):
        return _('{value} fixed-price enterprise discount').format(value=self.value)

#TODO: implement one free product benefit