import ddt
from django.core.management import call_command
from django.core.management.base import CommandError
from mock import patch
from oscar.core.loading import get_model

from ecommerce.extensions.test.factories import create_order
from ecommerce.tests.factories import PartnerFactory
from ecommerce.tests.testcases import TestCase

LOGGER_NAME = 'ecommerce.extensions.order.management.commands.update_order_lines_partner'
OrderLine = get_model('order', 'Line')


@ddt.ddt
class UpdateOrderLinePartnerTests(TestCase):
    """Tests for update_order_lines_partner management command."""

    PARTNER_CODE = 'testX'
    YES_NO_PATCH_LOCATION = 'ecommerce.extensions.order.management.commands.update_order_lines_partner.query_yes_no'

    def assert_error_log(self, error_msg, *args):
        """Helper to call command and assert error log."""
        with self.assertRaisesRegexp(CommandError, error_msg):
            call_command('update_order_lines_partner', *args)

    def test_partner_required(self):
        """Test that command raises partner required error."""
        self.assert_error_log(
            'Error: argument --partner is required',
            'sku12345'
        )

    def test_partner_does_not_exist(self):
        """Test that command raises partner does not exist error."""
        self.assert_error_log(
            'No Partner exists for code {}.'.format(self.PARTNER_CODE),
            'sku12345',
            '--partner={}'.format(self.PARTNER_CODE)
        )

    def test_one_or_more_sku_required(self):
        """Test that command raises one or more SKUs required error."""
        self.assert_error_log(
            'update_order_lines_partner requires one or more <SKU>s.',
            '--partner={}'.format(self.PARTNER_CODE)
        )

    @ddt.data(True, False)
    def test_update_order_lines_partner(self, yes_no_value):
        """Test that command works as expected."""
        new_partner = PartnerFactory(short_code=self.PARTNER_CODE)
        order = create_order()
        order_line = order.lines.first()
        self.assertNotEqual(order_line.partner, new_partner)
        with patch(self.YES_NO_PATCH_LOCATION) as mocked_yes_no:
            mocked_yes_no.return_value = yes_no_value
            call_command('update_order_lines_partner', order_line.partner_sku, '--partner={}'.format(self.PARTNER_CODE))
            order_line = OrderLine.objects.get(partner_sku=order_line.partner_sku)
            if yes_no_value:
                # Verify that partner is updated
                self.assertEqual(order_line.partner, new_partner)
                self.assertEqual(order_line.partner_name, new_partner.name)
            else:
                # Verify that partner is not updated
                self.assertNotEqual(order_line.partner, new_partner)
                self.assertNotEqual(order_line.partner_name, new_partner.name)
