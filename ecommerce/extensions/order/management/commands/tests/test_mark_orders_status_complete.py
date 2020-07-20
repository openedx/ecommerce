from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from oscar.core.loading import get_model
from testfixtures import LogCapture

from ecommerce.extensions.fulfillment.status import ORDER
from ecommerce.extensions.test.factories import create_order
from ecommerce.tests.testcases import TestCase

LOGGER_NAME = 'ecommerce.extensions.order.management.commands.mark_orders_status_complete'
MarkOrdersStatusCompleteConfig = get_model('order', 'MarkOrdersStatusCompleteConfig')
Order = get_model('order', 'Order')


class MarkOrdersStatusCompleteTests(TestCase):
    """
    Tests for `mark_orders_status_complete` command.
    """
    filename = 'orders_file.txt'

    def create_orders_file(self, order_numbers):
        """Create a file with order numbers with status `Fulfillment Error` - one per line"""
        with open(self.filename, 'w') as f:
            f.truncate(0)
            for order_number in order_numbers:
                # add to order numbers file
                f.write("%s\n" % order_number)

        f.close()

    def test_mark_orders_status_complete(self):
        """ Test that command successfully mark orders as completed."""
        order_numbers = []
        non_existant_order = 'NON-EXISTANT-ORDER'
        user = self.create_user()
        for __ in range(3):
            order = create_order(site=self.site, user=user, status=ORDER.FULFILLMENT_ERROR)
            order_numbers.append(order.number)

        completed_order = create_order(site=self.site, user=user, status=ORDER.COMPLETE)
        order_numbers.append(completed_order.number)
        order_numbers.append(non_existant_order)
        self.create_orders_file(order_numbers)

        orders = Order.objects.filter(status=ORDER.FULFILLMENT_ERROR)
        self.assertEqual(orders.count(), 3)

        with LogCapture(LOGGER_NAME) as log_capture:
            call_command(
                'mark_orders_status_complete', '--order-numbers-file={}'.format(self.filename)
            )

            log_capture.check_present(
                (
                    LOGGER_NAME,
                    'INFO',
                    '[Mark Orders Status Complete] Execution of command mark orders status complete is successful.\n'
                    'Total orders received: 5\n'
                    'Orders marked as completed: 3\n'
                    'Failed orders: {failed_orders}\n'
                    'Skipped orders: {skipped_orders}\n'.format(
                        failed_orders=non_existant_order,
                        skipped_orders=completed_order.number
                    )
                ),
            )

            # Verify that no orders exist with status `Fulfillment Error`
            orders = Order.objects.filter(status=ORDER.FULFILLMENT_ERROR)
            self.assertEqual(orders.count(), 0)

    def test_mark_orders_status_complete_from_config_model(self):
        """ Test that command successfully mark orders as completed using file from config model."""
        lines = ''
        user = self.create_user()
        for __ in range(3):
            order = create_order(site=self.site, user=user, status=ORDER.FULFILLMENT_ERROR)
            lines += '{}\n'.format(order.number)

        txt_file = SimpleUploadedFile(
            name='failed_orders.txt', content=lines.encode('utf-8'), content_type='text/plain'
        )
        MarkOrdersStatusCompleteConfig.objects.create(enabled=True, txt_file=txt_file)

        orders = Order.objects.filter(status=ORDER.FULFILLMENT_ERROR)
        self.assertEqual(orders.count(), 3)

        call_command('mark_orders_status_complete', '--file-from-database')

        orders = Order.objects.filter(status=ORDER.FULFILLMENT_ERROR)
        self.assertEqual(orders.count(), 0)

    def test_file_from_database_with_config_disabled(self):
        """
        Verify that command raises the CommandError if called with `--file-from-database`
        but config is disabled.
        """
        with self.assertRaises(CommandError):
            call_command('mark_orders_status_complete', '--file-from-database')

    def test_invalid_file_path(self):
        """
        Verify that command raises the CommandError for invalid file path.
        """
        with self.assertRaises(CommandError):
            call_command('mark_orders_status_complete', '--order-numbers-file={}'.format("invalid/order_id/file/path"))

        with self.assertRaises(CommandError):
            call_command('mark_orders_status_complete')

    def test_sleep_time(self):
        """
        Verify sleep time log.
        """
        self.create_orders_file(['EDX-22323'])
        with LogCapture(LOGGER_NAME) as log_capture:
            call_command(
                'mark_orders_status_complete',
                '--order-numbers-file={}'.format(self.filename),
                '--sleep-time=1'
            )

            log_capture.check_present(
                (
                    LOGGER_NAME,
                    'INFO',
                    '[Mark Orders Status Complete] '
                    'Sleeping for 1 seconds'
                )
            )
