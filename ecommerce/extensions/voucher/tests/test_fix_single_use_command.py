# encoding: utf-8
"""Contains the tests for fix_single_use command."""
from django.core.management import call_command
from mock import patch

from oscar.core.loading import get_model

from ecommerce.extensions.test.factories import prepare_voucher
from ecommerce.tests.mixins import CouponMixin
from ecommerce.tests.testcases import TestCase

Voucher = get_model('voucher', 'Voucher')
COUPON_CODE = 'COUPONTEST'


class FixSingleUseVoucherTests(CouponMixin, TestCase):
    """Tests the fix_single_use command."""
    def setUp(self):
        super(FixSingleUseVoucherTests, self).setUp()

    def test_command_called_successfully(self):
        """ Verify command runs. """
        with patch('ecommerce.extensions.voucher.management.commands.fix_single_use.Command') as mock_call_command:
            call_command('fix_single_use')
            self.assertTrue(mock_call_command.called)

    def assert_command_execution(self, usage, max_usage, expected_before, expected_after):
        """ Assert offer max_global_applications value changed after the command call. """
        voucher, __ = prepare_voucher(code=COUPON_CODE, usage=usage, max_usage=max_usage)
        offer_before = voucher.offers.first()
        self.assertEqual(offer_before.max_global_applications, expected_before)

        call_command('fix_single_use')
        offer_after = voucher.offers.first()
        self.assertEqual(offer_after.max_global_applications, expected_after)

    def test_offer_changed(self):
        """ Verify the offer has changed. """
        self.assert_command_execution(Voucher.SINGLE_USE, 1, 1, None)

    def test_offer_unchanged(self):
        """ Verify voucher other than SINGLE_USE are left unaffected. """
        self.assert_command_execution(Voucher.ONCE_PER_CUSTOMER, 1, 1, 1)
