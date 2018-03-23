import logging

from requests.exceptions import ConnectionError, Timeout

from ecommerce.extensions.analytics.utils import audit_log
from ecommerce.extensions.fulfillment.modules import BaseFulfillmentModule
from ecommerce.extensions.fulfillment.status import LINE
from ecommerce.journal.client import post_journal_access


logger = logging.getLogger(__name__)


class JournalFulfillmentModule(BaseFulfillmentModule):
    """ Fulfillment Module for granting learner access to a Journal """

    def supports_line(self, line):
        logger.debug('Line order: [%s], is journal: [%s]', line, line.product.is_journal_product)
        return line.product.is_journal_product

    def get_supported_lines(self, lines):
        """ Return a list of lines that can be fulfilled.
        Checks each line to determine if it is a "Journal". Journals are fulfilled by
        giving the use access to the specified journal.
        Args:
            lines (List of Lines): Order Lines, associated with purchased products in an Order.
        Returns:
            A supported list of unmodified lines associated with "Journal" products.
        """

        return [line for line in lines if self.supports_line(line)]

    def fulfill_product(self, order, lines):
        """ Fulfills the purchase of a 'Journal'
        Args:
            order (Order): The Order associated with the lines to be fulfilled.  The user associated with the order is
                presumed to be the student to grant access to the journal
            lines (List of Lines): Order Lines, associated with purchased products in the Order.  These should only be
                'Journal' products.
        Returns:
            The original set of lines, with new statuses set based on the success or failure of fulfillment.
        """
        logger.info('Attempting to fulfill "Journal" product types for order [%s]', order.number)

        for line in lines:
            try:
                journal_uuid = line.product.attr.UUID
            except AttributeError:
                logger.error('Journal Product does not have required attributes, [uuid]')
                line.set_status(LINE.FULFILLMENT_CONFIGURATION_ERROR)
                continue

            try:
                post_journal_access(
                    site_configuration=order.site.siteconfiguration,
                    order_number=order.number,
                    username=order.user.username,
                    journal_uuid=journal_uuid
                )

                line.set_status(LINE.COMPLETE)

                audit_log(
                    'line_fulfilled',
                    order_line_id=line.id,
                    order_number=order.number,
                    product_class=line.product.get_product_class().name,
                    user_id=order.user.id,
                    journal_uuid=journal_uuid,
                )
            except (Timeout, ConnectionError):
                logger.exception(
                    'Unable to fulfill line [%d] of order [%s] due to a network problem',
                    line.id,
                    order.number
                )
                line.set_status(LINE.FULFILLMENT_NETWORK_ERROR)
            except Exception:
                logger.exception(
                    'Unable to fulfill line [%d] of order [%s]',
                    line.id,
                    order.number
                )
                line.set_status(LINE.FULFILLMENT_SERVER_ERROR)

        logger.info('Finished fulfilling "Journal" product types for order [%s]', order.number)
        return order, lines

    def revoke_line(self, line):
        logger.error('REVOKE LINE')
        return False
