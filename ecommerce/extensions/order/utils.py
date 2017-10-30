"""Order Utility Classes. """
from __future__ import unicode_literals

import logging

import waffle
from oscar.apps.order.utils import OrderCreator as OscarOrderCreator
from oscar.core.loading import get_model
from threadlocals.threadlocals import get_current_request

from ecommerce.extensions.order.constants import DISABLE_REPEAT_ORDER_CHECK_SWITCH_NAME
from ecommerce.extensions.refund.status import REFUND_LINE
from ecommerce.referrals.models import Referral

logger = logging.getLogger(__name__)

Order = get_model('order', 'Order')
OrderLine = get_model('order', 'Line')
RefundLine = get_model('refund', 'RefundLine')


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
    def create_order_model(self, user, basket, shipping_address, shipping_method, shipping_charge, billing_address,
                           total, order_number, status, **extra_order_fields):
        """
        Create an order model.

        This override ensures the order's site is set to that of the basket. If the basket has no site, the default
        site is used. The site value can be overridden by setting the `site` kwarg.
        """

        # If a site was not passed in with extra_order_fields,
        # use the basket's site if it has one, else get the site
        # from the current request.
        site = basket.site
        if not site:
            site = get_current_request().site

        order_data = {'basket': basket,
                      'number': order_number,
                      'site': site,
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
        if extra_order_fields:
            order_data.update(extra_order_fields)
        order = Order(**order_data)
        order.save()

        try:
            referral = Referral.objects.get(basket=basket)
            referral.order = order
            referral.save()
        except Referral.DoesNotExist:
            logger.debug('Order [%d] has no referral associated with its basket.', order.id)
        except Exception:  # pylint: disable=broad-except
            logger.exception('Referral for Order [%d] failed to save.', order.id)

        return order


class UserAlreadyPlacedOrder(object):
    """
    Provides utils methods to check if user has already placed an order
    """

    @staticmethod
    def user_already_placed_order(user, product):
        """
        Checks if the user has already purchased the product.

        A product is considered purchased if an OrderLine exists for the product,
        and it has not been refunded.

        Args:
            user: (User)
            product: (Product)

        Returns:
            bool: True if user has purchased the product.

        Notes:
            If the switch with the name `ecommerce.extensions.order.constants.DISABLE_REPEAT_ORDER_SWITCH_NAME`
            is active this check will be disabled, and this method will already return `False`.
        """
        if waffle.switch_is_active(DISABLE_REPEAT_ORDER_CHECK_SWITCH_NAME):
            return False

        orders_lines = OrderLine.objects.filter(product=product, order__user=user)
        if orders_lines:
            for order_line in orders_lines:
                if (not UserAlreadyPlacedOrder.is_order_line_refunded(order_line) and
                        not order_line.product.is_course_entitlement_product):
                    return True

        return False

    @staticmethod
    def is_order_line_refunded(order_line):
        """
        checks if the order line is refunded
        Returns:
            boolean: True if order line is refunded else false
        """
        return RefundLine.objects.filter(order_line=order_line, status=REFUND_LINE.COMPLETE).exists()
