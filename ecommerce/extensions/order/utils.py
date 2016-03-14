"""Order Utility Classes. """
from __future__ import unicode_literals
import logging

from oscar.apps.order.utils import OrderCreator as OscarOrderCreator
from oscar.core.loading import get_model
from threadlocals.threadlocals import get_current_request

logger = logging.getLogger(__name__)

Order = get_model('order', 'Order')


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
            site = get_current_request().site
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
    def create_order_model(self, user, basket, shipping_address, shipping_method, shipping_charge,
                           billing_address, total, order_number, status, **extra_order_fields):
        """
        Create an order model.

        This override ensures the order's site is set to that of the basket. If the basket has no
        site, the default site is used. The site value can be overridden by setting the `site` kwarg.

        NOTE:
        Most of what follows is a duplication of the OrderCreator.create_order_model implementation,
        with some modification to actually support the site override expectation mentioned above.

        See the following links for more information on why we've done this:
            * https://github.com/django-oscar/django-oscar/issues/2013
            * https://github.com/django-oscar/django-oscar/pulls/2014

        When the update has been made in the upstream django-oscar project, and a new version has
        been released, we can revert to the original call to super that existed in this override.
        """

        order_data = {'basket': basket,
                      'number': order_number,
                      'currency': total.currency,
                      'total_incl_tax': total.incl_tax,
                      'total_excl_tax': total.excl_tax,
                      'shipping_incl_tax': shipping_charge.incl_tax,
                      'shipping_excl_tax': shipping_charge.excl_tax,
                      'shipping_method': shipping_method.name,
                      'shipping_code': shipping_method.code}
        if shipping_address:
            order_data['shipping_address'] = shipping_address
        if billing_address:
            order_data['billing_address'] = billing_address
        if user and user.is_authenticated():
            order_data['user_id'] = user.id
        if status:
            order_data['status'] = status

        # Append any additional fields provided by the caller to the order data container
        if extra_order_fields:
            order_data.update(extra_order_fields)

        # If no site was explicitly provided, attempt to locate one in the provided basket.
        if basket.site and 'site' not in order_data:
            order_data['site'] = basket.site

        # If we still don't have a site, grab the current site from the Django Sites framework
        if 'site' not in order_data:
            order_data['site'] = get_current_request().site

        # Create and store a new order model, then hand it back to the caller
        order = Order(**order_data)
        order.save()
        return order
