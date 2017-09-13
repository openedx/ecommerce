import operator

from django.utils.translation import ugettext_lazy as _


class BenefitWithoutRangeMixin(object):
    """ Mixin for Benefits without an attached range.

    The range is only used for the name and description. We would prefer not
    to deal with ranges since we rely on the condition to fully determine if
    a conditional offer is applicable to a basket.
    """
    def get_applicable_lines(self, offer, basket, range=None):  # pylint: disable=unused-argument,redefined-builtin
        condition = offer.condition.proxy() or offer.condition
        line_tuples = condition.get_applicable_lines(offer, basket, most_expensive_first=False)

        # Do not allow multiple discounts per line
        line_tuples = [line_tuple for line_tuple in line_tuples if line_tuple[1].quantity_without_discount > 0]

        # We sort lines to be cheapest first to ensure consistent applications
        return sorted(line_tuples, key=operator.itemgetter(0))

    @property
    def name(self):
        return _('{value}% {app_label} discount').format(
            value=self.value,
            app_label=self._meta.app_label
        )
