"""Order Utility Classes. """


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

        # TODO add partner code instead of hard coded value
        # after updating basket modal
        # partner_code = basket.Basket.objects.get(pk=basket.id).parnter.short_code

        partner_code = 'edx'
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
