""" Fulfillment API for processing orders

Common interface designed to allow the fulfillment of orders for any type of product introduced into our catalog.
Calls down to a common interface for fulfillment of each line of an order based on a product type to determine if we
can successfully fulfill the product. Success can be reported back based on each line item in the order.

"""


import logging
from importlib import import_module

from django.conf import settings
from django.utils.timezone import now

from ecommerce.extensions.fulfillment import exceptions
from ecommerce.extensions.fulfillment.status import LINE, ORDER
from ecommerce.extensions.refund.status import REFUND_LINE

logger = logging.getLogger(__name__)


def fulfill_order(order, lines, email_opt_in=False):
    """ Fulfills line items in an Order

    Attempts to fulfill the products in the Order. Checks the mapping of fulfillment modules to product types, and
    will fulfill the order line items in the specified order. If a line item cannot be fulfilled, either because
    of an error, or no existing fulfillment logic, the Order is marked with "Fulfillment Error" and the status of
    each line is marked according to its success or failure.

    Args:
        order (Order): The Order associated with this line item. The status of the Order may be altered based on
            fulfilling the line items.
        lines (List of Lines): A list of Line items in the Order that should be fulfilled.
        email_opt_in (bool): Whether the user should be opted in to emails as
            part of the fulfillment. Defaults to False.

    Returns:
        The modified Order and Lines. The status of the Order, or any given Line item, may be 'Complete', or
        'Fulfillment Error' based on the result of the fulfillment attempt.

    """
    logger.info("Attempting to fulfill products for order [%s]", order.number)
    if ORDER.COMPLETE not in order.available_statuses():
        error_msg = "Order has a current status of [{status}] which cannot be fulfilled.".format(status=order.status)
        logger.error(error_msg)
        raise exceptions.IncorrectOrderStatusError(error_msg)

    # Construct a dict of lines by their product type.
    line_items = list(lines.all())

    try:
        # Iterate over the Fulfillment Modules defined in our configuration and determine if they support
        # any of the lines in the order. Fulfill line items in the order they are designated by the configuration.
        # Remaining line items should be marked with a fulfillment error since we have no configuration that
        # allows them to be fulfilled.
        for module_class in get_fulfillment_modules():
            module = module_class()
            supported_lines = module.get_supported_lines(line_items)
            if supported_lines:
                line_items = list(set(line_items) - set(supported_lines))
                module.fulfill_product(order, supported_lines, email_opt_in=email_opt_in)

        # Check to see if any line items in the order have not been accounted for by a FulfillmentModule
        # Any product does not line up with a module, we have to mark a fulfillment error.
        for line in line_items:
            product_type = line.product.get_product_class().name
            logger.error("Product Type [%s] does not have an associated Fulfillment Module. It cannot be fulfilled.",
                         product_type)
            line.set_status(LINE.FULFILLMENT_CONFIGURATION_ERROR)
    except Exception:  # pylint: disable=broad-except
        logger.exception('An unexpected error occurred while fulfilling order [%s].', order.number)
    finally:
        # Check if all lines are successful, or there were errors, and set the status of the Order.
        order_status = ORDER.COMPLETE
        for line in lines.all():
            if line.status != LINE.COMPLETE:
                logger.error('There was an error while fulfilling order [%s]', order.number)
                order_status = ORDER.FULFILLMENT_ERROR
                break

        order.set_status(order_status)

        elapsed = now() - order.date_placed
        logger.info(
            "Finished fulfilling order [%s] with status [%s]. [%s] seconds elapsed since placement.",
            order.number,
            order.status,
            elapsed.total_seconds()
        )

        return order  # pylint: disable=lost-exception


def get_fulfillment_modules():
    """ Retrieves all fulfillment modules declared in settings. """
    module_paths = getattr(settings, 'FULFILLMENT_MODULES', [])
    modules = []

    for cls_path in module_paths:
        try:
            module_path, _, name = cls_path.rpartition('.')
            module = getattr(import_module(module_path), name)
            modules.append(module)
        except (ImportError, ValueError, AttributeError):
            logger.exception("Could not load module at [%s]", cls_path)

    return modules


def get_fulfillment_modules_for_line(line):
    """
    Returns a list of fulfillment modules that can fulfill the given Line.

    Arguments
        line (Line): Line to be considered for fulfillment.
    """
    return [module for module in get_fulfillment_modules() if module().supports_line(line)]


def revoke_fulfillment_for_refund(refund):
    """
    Revokes fulfillment for all lines in a refund.

    Returns
        Boolean: True, if revocation of all lines succeeded; otherwise, False.
    """
    succeeded = True

    # Refunds corresponding to a total credit of $0 require no revocation. This also
    # prevents deadlocking with the LMS which occurs when Otto attempts to revoke an
    # automatically-approved refund.
    if refund.total_credit_excl_tax == 0:
        for refund_line in refund.lines.all():
            refund_line.set_status(REFUND_LINE.COMPLETE)
    else:
        # TODO (CCB): As our list of product types and fulfillment modules grows, this may become slow,
        # and should be updated. Runtime is O(n^2).
        for refund_line in refund.lines.all():
            order_line = refund_line.order_line
            modules = get_fulfillment_modules_for_line(order_line)

            for module in modules:
                if module().revoke_line(order_line):
                    refund_line.set_status(REFUND_LINE.COMPLETE)
                else:
                    succeeded = False
                    refund_line.set_status(REFUND_LINE.REVOCATION_ERROR)

    return succeeded
