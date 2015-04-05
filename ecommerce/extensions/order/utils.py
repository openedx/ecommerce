"""Order Utility Classes. """
from django.conf import settings


class OrderNumberGenerator(object):
    """Simple object for generating order numbers.

    We need this as the order number is often required for payment
    which takes place before the order model has been created.

    """

    @staticmethod
    def order_number(basket):
        """Create an order number with a configured prefix.

        Creates a unique order number with a configured prefix.

        Args:
            basket (Basket): Used to construct the order ID.

        Returns:
            String: representation of the order 'number' with a configured prefix.

        """
        prefix = getattr(settings, 'ORDER_NUMBER_PREFIX', 'OSCR')
        order_id = str(100000 + basket.id)
        return u"{prefix}-{order_id}".format(prefix=prefix, order_id=order_id)
