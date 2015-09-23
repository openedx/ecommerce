"""Order Utility Classes. """
from oscar.core.loading import get_model


class OrderNumberGenerator(object):
    """Simple object for generating order numbers.

    We need this as the order number is often required for payment
    which takes place before the order model has been created.
    """
    OFFSET = 100000

    def order_number(self, basket):
        """Create an order number with a configured prefix.

        Creates a unique order number with a configured prefix.

        Arguments:
            basket (Basket): Used to construct the order ID.

        Returns:
            str: Representation of the order 'number' with a configured prefix.

        """
        order_id = basket.id + self.OFFSET

        # Import here to avoid circular imports between 'order' and 'basket' apps
        Basket = get_model('basket', 'Basket')
        partner_code = Basket.objects.get(pk=basket.id).partner.short_code

        order_number = u'{partner_code}-{order_id}'.format(partner_code=partner_code, order_id=order_id)

        return order_number

    def basket_id(self, order_number):
        """Inverse of order number generation.

        Given an order number, returns the basket ID used when generating it.

        Arguments:
            order_number (str): An order number.

        Returns:
            int: The basket ID used to generate the provided order number.
        """

        order_id = int(order_number.rsplit('-', 1)[1])
        basket_id = order_id - self.OFFSET

        return basket_id
