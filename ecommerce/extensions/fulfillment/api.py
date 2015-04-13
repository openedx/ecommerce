""" Fulfillment API for processing orders

Common interface designed to allow the fulfillment of orders for any type of product introduced into our catalog.
Calls down to a common interface for fulfillment of each line of an order based on a product type to determine if we
can successfully fulfill the product. Success can be reported back based on each line item in the order.

"""
import logging

from django.conf import settings
from django.utils import importlib

from ecommerce.extensions.fulfillment import exceptions
from ecommerce.extensions.fulfillment.status import ORDER, LINE


logger = logging.getLogger(__name__)


def fulfill_order(order, lines):
    """ Fulfills line items in an Order

    Attempts to fulfill the products in the Order. Checks the mapping of fulfillment modules to product types, and
    will fulfill the order line items in the specified order. If a line item cannot be fulfilled, either because
    of an error, or no existing fulfillment logic, the Order is marked with "Fulfillment Error" and the status of
    each line is marked according to its success or failure.

    Args:
        order (Order): The Order associated with this line item. The status of the Order may be altered based on
            fulfilling the line items.
        lines (List of Lines): A list of Line items in the Order that should be fulfilled.

    Returns:
        The modified Order and Lines. The status of the Order, or any given Line item, may be 'Complete', or
        'Fulfillment Error' based on the result of the fulfillment attempt.

    """
    logger.info("Attempting to fulfill products for order [%s]", order.number)
    if ORDER.COMPLETE not in order.available_statuses():
        error_msg = "Order has a current status of [{status}] which cannot be fulfilled.".format(status=order.status)
        logger.error(error_msg)
        raise exceptions.IncorrectOrderStatusError(error_msg)
    modules = getattr(settings, 'FULFILLMENT_MODULES', {})

    # Construct a dict of lines by their product type.
    line_items = list(lines.all())

    try:
        # Iterate over the Fulfillment Modules defined in our configuration and determine if they support
        # any of the lines in the order. Fulfill line items in the order they are designated by the configuration.
        # Remaining line items should be marked with a fulfillment error since we have no configuration that
        # allows them to be fulfilled.
        for cls_path in modules:
            try:
                module_path, _, name = cls_path.rpartition('.')
                module = getattr(importlib.import_module(module_path), name)
                supported_lines = module().get_supported_lines(order, line_items)
                line_items = list(set(line_items) - set(supported_lines))
                module().fulfill_product(order, supported_lines)
            except (ImportError, ValueError, AttributeError):
                logger.exception("Could not load module at [%s]", cls_path)

        # Check to see if any line items in the order have not been accounted for by a FulfillmentModule
        # Any product does not line up with a module, we have to mark a fulfillment error.
        for line in line_items:
            product_type = line.product.product_class.name
            logger.error("Product Type [%s] in order does not have an associated Fulfillment Module", product_type)
            line.set_status(LINE.FULFILLMENT_CONFIGURATION_ERROR)
    finally:
        # Check if all lines are successful, or there were errors, and set the status of the Order.
        order_status = ORDER.COMPLETE
        for line in lines.all():
            if line.status != LINE.COMPLETE:
                logger.error('There was an error while fulfilling order [%s]', order.number)
                order_status = ORDER.FULFILLMENT_ERROR
                break
        order.set_status(order_status)
        logger.info("Finished fulfilling order [%s] with status [%s]", order.number, order.status)
        return order  # pylint: disable=lost-exception


def revoke_order(order, lines):  # pylint: disable=unused-argument
    """ Revokes line items an Order.

    Attempts to revoke the products in the specified order. This logically may only work for digital products, where
    we can revoke access. How revoking works per product will have to be carefully defined when this function is used.

    Args:
        order (Order): The Order associated with this line item. The status of the Order may be altered based on
            revoking the line items.
        lines (List of Lines): A list of Line items in the Order that should be revoked.

    Returns:
        The modified Order and Lines.
    """
    pass  # pragma: no cover
