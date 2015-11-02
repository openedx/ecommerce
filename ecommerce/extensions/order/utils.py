"""Order Utility Classes. """
from __future__ import unicode_literals
import logging

from django.contrib.sites.models import Site
from oscar.apps.order.utils import OrderCreator as OscarOrderCreator

logger = logging.getLogger(__name__)


class OrderNumberGenerator(object):
    OFFSET = 100000

    def order_number(self, basket):
        """
        Returns an order number, determined using the basket's ID and site.

        Arguments:
            basket (Basket)

        Returns:
            string: Order number
        """
        site = basket.site
        if not site:
            site = Site.objects.get_current()
            logger.warning('Basket [%d] is not associated with a Site. Defaulting to Site [%d].', basket.id, site.id)

        partner = site.siteconfiguration.partner
        return self.order_number_from_basket_id(partner, basket.id)

    def order_number_from_basket_id(self, partner, basket_id):
        """
        Return an order number for a given basket ID.

        Arguments:
            basket_id (int): Basket identifier.

        Returns:
            string: Order number.
        """
        order_id = int(basket_id) + self.OFFSET
        return u'{prefix}-{order_id}'.format(prefix=partner.short_code.upper(), order_id=order_id)

    def basket_id(self, order_number):
        """Inverse of order number generation.

        Given an order number, returns the basket ID used when generating it.

        Arguments:
            order_number (str): An order number.

        Returns:
            int: The basket ID used to generate the provided order number.
        """
        order_id = int(order_number.split('-')[1])
        return order_id - self.OFFSET


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
