"""Order Utility Classes. """
from __future__ import unicode_literals
from django.conf import settings
from oscar.apps.order.utils import OrderCreator as OscarOrderCreator


class OrderNumberGenerator(object):
    """Simple object for generating order numbers.

    We need this as the order number is often required for payment
    which takes place before the order model has been created.
    """
    OFFSET = 100000

    def order_number(self, basket):
        return self.order_number_from_basket_id(basket.id)

    def order_number_from_basket_id(self, basket_id):
        """
        Return an order number for a given basket ID.

        Arguments:
            basket_id (int): Basket identifier.

        Returns:
            string: Order number.
        """
        order_id = int(basket_id) + self.OFFSET
        return u'{prefix}-{order_id}'.format(prefix=settings.ORDER_NUMBER_PREFIX, order_id=order_id)

    def basket_id(self, order_number):
        """Inverse of order number generation.

        Given an order number, returns the basket ID used when generating it.

        Arguments:
            order_number (str): An order number.

        Returns:
            int: The basket ID used to generate the provided order number.
        """
        order_id = int(order_number.lstrip(u'{prefix}-'.format(prefix=settings.ORDER_NUMBER_PREFIX)))
        basket_id = order_id - self.OFFSET

        return basket_id


class OrderCreator(OscarOrderCreator):
    def create_order_model(self, user, basket, shipping_address, shipping_method, shipping_charge, billing_address,
                           total, order_number, status, **extra_order_fields):
        """
        Create an order model.

        This override ensures the order's site is set to that of the basket. If the basket has no site, the default
        site is used. The site value can be overridden by setting the `site` kwarg.
        """

        # Pull the order's site from the basket, if the basket has a site and
        # a site is not already being explicitly set.
        if basket.site and 'site' not in extra_order_fields:
            extra_order_fields['site'] = basket.site

        return super(OrderCreator, self).create_order_model(
            user, basket, shipping_address, shipping_method, shipping_charge, billing_address, total, order_number,
            status, **extra_order_fields)
