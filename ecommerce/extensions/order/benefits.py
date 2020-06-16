

from django.utils.translation import ugettext_lazy as _
from oscar.core.loading import get_model

from ecommerce.extensions.offer.mixins import BenefitWithoutRangeMixin, PercentageBenefitMixin

PercentageDiscountBenefit = get_model('offer', 'PercentageDiscountBenefit')


class ManualEnrollmentOrderDiscountBenefit(BenefitWithoutRangeMixin, PercentageBenefitMixin, PercentageDiscountBenefit):
    """ Manual course enrollment related PercentageDiscountBenefit without an attached range. """

    class Meta:
        app_label = 'order'
        proxy = True

    @property
    def name(self):
        # NOTE: We are not using str.format() because gettext incorrectly parses the string,
        # resulting in translation compilation errors.
        return _('%d%% discount for manual course enrollment order') % self.value
