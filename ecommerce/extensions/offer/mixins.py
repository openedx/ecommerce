

import operator

from oscar.core.loading import get_model

Benefit = get_model('offer', 'Benefit')


class BenefitWithoutRangeMixin:
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


class ConditionWithoutRangeMixin:
    """ Mixin for Conditions without an attached range.

    The range is only used for the name and description. We would prefer not
    to deal with ranges since we rely on the condition to fully determine if
    a conditional offer is applicable to a basket.
    """
    def can_apply_condition(self, line):
        """
        Determines whether the condition can be applied to a given basket line.
        """
        if not line.stockrecord_id:
            return False
        return line.product.get_is_discountable()


class AbsoluteBenefitMixin:
    """ Mixin for fixed-amount Benefits. """
    benefit_class_type = Benefit.FIXED


class PercentageBenefitMixin:
    """ Mixin for percentage-based Benefits. """
    benefit_class_type = Benefit.PERCENTAGE


class SingleItemConsumptionConditionMixin:

    def consume_items(self, offer, basket, affected_lines):  # pylint: disable=unused-argument
        """ Marks items within the basket lines as consumed so they can't be reused in other offers.

        This offer will consume only 1 unit of quantity for each affected line.

        Args:
            offer (AbstractConditionalOffer)
            basket (AbstractBasket)
            affected_lines (tuple[]): The lines that have been affected by the discount.
                This should be list of tuples (line, discount, qty)
        """
        for line, _, __ in affected_lines:
            quantity_to_consume = min(line.quantity_without_discount, 1)
            line.consume(quantity_to_consume)
