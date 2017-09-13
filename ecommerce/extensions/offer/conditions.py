class SingleItemConsumptionConditionMixin(object):

    def consume_items(self, offer, basket, affected_lines):  # pylint: disable=unused-argument
        """ Marks items within the basket lines as consumed so they can't be reused in other offers.

        This offer will consume only 1 unit of quantity for each affected line.

        Args:
            offer (AbstractConditionalOffer)
            basket (AbstractBasket)
            affected_lines (tuple[]): The lines that have been affected by the discount.
                This should be list of tuples (line, discount, qty)
        """
        for line, __, __ in affected_lines:
            quantity_to_consume = min(line.quantity_without_discount, 1)
            line.consume(quantity_to_consume)
