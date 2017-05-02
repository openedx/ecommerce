import operator

from django.utils.translation import ugettext_lazy as _
from oscar.apps.offer.benefits import AbsoluteDiscountBenefit, PercentageDiscountBenefit


class ConditionBasedApplicationMixin(object):
    def get_applicable_lines(self, offer, basket, range=None):  # pylint: disable=unused-argument,redefined-builtin
        condition = offer.condition.proxy() or offer.condition
        line_tuples = condition.get_applicable_lines(offer, basket, most_expensive_first=False)

        # Do not allow multiple discounts per line
        line_tuples = [line_tuple for line_tuple in line_tuples if line_tuple[1].quantity_without_discount > 0]

        # We sort lines to be cheapest first to ensure consistent applications
        return sorted(line_tuples, key=operator.itemgetter(0))


class PercentageDiscountBenefitWithoutRange(ConditionBasedApplicationMixin, PercentageDiscountBenefit):
    """ PercentageDiscountBenefit without an attached range.

    The range is only used for the name and description. We would prefer not
    to deal with ranges since we rely on the condition to fully determine if
    a conditional offer is applicable to a basket.
    """

    class Meta(object):
        app_label = 'programs'
        proxy = True

    @property
    def name(self):
        return _('{value}% program discount').format(value=self.value)


class AbsoluteDiscountBenefitWithoutRange(ConditionBasedApplicationMixin, AbsoluteDiscountBenefit):
    """ AbsoluteDiscountBenefit without an attached range.

       The range is only used for the name and description. We would prefer not
       to deal with ranges since we rely on the condition to fully determine if
       a conditional offer is applicable to a basket.
       """

    class Meta(object):
        app_label = 'programs'
        proxy = True

    @property
    def name(self):
        return _('{value} fixed-price program discount').format(value=self.value)
