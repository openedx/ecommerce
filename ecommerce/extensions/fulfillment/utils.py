""" Fulfillment Utility Methods. """

from __future__ import absolute_import

from decimal import Decimal


def get_enterprise_customer_cost_for_line(list_price, effective_discount_percentage):
    """
    Calculates the enterprise customer cost on a particular line item list price.

    Args:
        list_price: a Decimal object
        effective_discount_percentage: A Decimal() object. Is expected to
            be a decimaled percent (as in, .45 (representing 45 percent))

    Returns:
        A Decimal() object.
    """
    cost = list_price * (Decimal('1.00000') - effective_discount_percentage)

    # Round to 5 decimal places.
    return cost.quantize(Decimal('.00001'))
