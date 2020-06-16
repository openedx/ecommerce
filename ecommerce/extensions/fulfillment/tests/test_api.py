"""Tests for the Fulfillment API"""


import ddt
from django.test.utils import override_settings
from mock import patch
from testfixtures import LogCapture

from ecommerce.extensions.fulfillment import api, exceptions
from ecommerce.extensions.fulfillment.api import (
    get_fulfillment_modules,
    get_fulfillment_modules_for_line,
    revoke_fulfillment_for_refund
)
from ecommerce.extensions.fulfillment.status import LINE, ORDER
from ecommerce.extensions.fulfillment.tests.mixins import FulfillmentTestMixin
from ecommerce.extensions.fulfillment.tests.modules import FakeFulfillmentModule
from ecommerce.extensions.refund.status import REFUND, REFUND_LINE
from ecommerce.extensions.refund.tests.factories import RefundFactory
from ecommerce.tests.testcases import TestCase


@ddt.ddt
class FulfillmentApiTests(FulfillmentTestMixin, TestCase):
    """ Tests for the fulfillment.api module. """

    def setUp(self):
        super(FulfillmentApiTests, self).setUp()
        self.order = self.generate_open_order()

    @override_settings(FULFILLMENT_MODULES=['ecommerce.extensions.fulfillment.tests.modules.FakeFulfillmentModule', ])
    def test_fulfill_order_successful_fulfillment(self):
        """ Test a successful fulfillment of an order. """
        api.fulfill_order(self.order, self.order.lines)
        self.assert_order_fulfilled(self.order)

    def test_donation_fulfill_order_successful_fulfillment(self):
        """ Test a successful fulfillment of a donation order. """
        order_with_donation = self.generate_open_order(product_class="Donation")
        api.fulfill_order(order_with_donation, order_with_donation.lines)
        self.assert_order_fulfilled(order_with_donation)

    @override_settings(FULFILLMENT_MODULES=['ecommerce.extensions.fulfillment.tests.modules.FakeFulfillmentModule', ])
    def test_fulfill_order_bad_fulfillment_state(self):
        """Test a basic fulfillment of a Course Seat."""
        # Set the order to Complete, which cannot be fulfilled.
        self.order.set_status(ORDER.COMPLETE)
        with self.assertRaises(exceptions.IncorrectOrderStatusError):
            api.fulfill_order(self.order, self.order.lines)

    @override_settings(FULFILLMENT_MODULES=['ecommerce.extensions.fulfillment.tests.modules.FulfillNothingModule', ])
    def test_fulfill_order_unknown_product_type(self):
        """Test an unknown product type."""
        api.fulfill_order(self.order, self.order.lines)
        self.assertEqual(ORDER.FULFILLMENT_ERROR, self.order.status)
        self.assertEqual(LINE.FULFILLMENT_CONFIGURATION_ERROR, self.order.lines.all()[0].status)

    @override_settings(FULFILLMENT_MODULES=['ecommerce.extensions.fulfillment.tests.modules.NotARealModule', ])
    def test_fulfill_order_incorrect_module(self):
        """Test an incorrect Fulfillment Module."""
        api.fulfill_order(self.order, self.order.lines)
        self.assertEqual(ORDER.FULFILLMENT_ERROR, self.order.status)
        self.assertEqual(LINE.FULFILLMENT_CONFIGURATION_ERROR, self.order.lines.all()[0].status)

    @override_settings(FULFILLMENT_MODULES=['ecommerce.extensions.fulfillment.tests.modules.FakeFulfillmentModule', ])
    @patch('ecommerce.extensions.fulfillment.tests.modules.FakeFulfillmentModule.get_supported_lines')
    def test_fulfill_order_invalid_module(self, mocked_method):
        """Verify an exception is logged when an unexpected error occurs."""
        mocked_method.return_value = Exception
        with patch('ecommerce.extensions.fulfillment.api.logger.exception') as mock_logger:
            api.fulfill_order(self.order, self.order.lines)
            self.assertEqual(ORDER.FULFILLMENT_ERROR, self.order.status)
            self.assertTrue(mock_logger.called)

    @override_settings(FULFILLMENT_MODULES=['ecommerce.extensions.fulfillment.tests.modules.FakeFulfillmentModule',
                                            'ecommerce.extensions.fulfillment.tests.modules.NotARealModule'])
    def test_get_fulfillment_modules(self):
        """
        Verify the function retrieves the modules specified in settings.
        An error should be logged for modules that cannot be loaded.
        """
        logger_name = 'ecommerce.extensions.fulfillment.api'

        with LogCapture(logger_name) as logger:
            actual = get_fulfillment_modules()

            # Only FakeFulfillmentModule should be loaded since it is the only real class.
            self.assertEqual(actual, [FakeFulfillmentModule])

            # An error should be logged for NotARealModule since it cannot be loaded.
            logger.check((
                logger_name,
                'ERROR',
                'Could not load module at [ecommerce.extensions.fulfillment.tests.modules.NotARealModule]'
            ))

    @override_settings(FULFILLMENT_MODULES=['ecommerce.extensions.fulfillment.tests.modules.FakeFulfillmentModule',
                                            'ecommerce.extensions.fulfillment.tests.modules.FulfillNothingModule'])
    def test_get_fulfillment_modules_for_line(self):
        """
        Verify the function returns an array of fulfillment modules that can fulfill a specific line.
        """
        line = self.order.lines.first()
        actual = get_fulfillment_modules_for_line(line)
        self.assertEqual(actual, [FakeFulfillmentModule])

    @override_settings(FULFILLMENT_MODULES=['ecommerce.extensions.fulfillment.tests.modules.FakeFulfillmentModule'])
    def test_revoke_fulfillment_for_refund(self):
        """
        Verify the function revokes fulfillment for all lines in a refund.
        """
        refund = RefundFactory(status=REFUND.PAYMENT_REFUNDED)
        self.assertTrue(revoke_fulfillment_for_refund(refund))
        self.assertEqual(refund.status, REFUND.PAYMENT_REFUNDED)
        self.assertEqual({line.status for line in refund.lines.all()}, {REFUND_LINE.COMPLETE})

    @override_settings(FULFILLMENT_MODULES=[])
    def test_suppress_revocation_for_zero_dollar_refund(self):
        """
        Verify that the function does not require use of fulfillment modules to mark lines in a refund
        corresponding to a total credit of $0 as complete.
        """
        refund = RefundFactory(status=REFUND.PAYMENT_REFUNDED)
        refund.total_credit_excl_tax = 0
        refund.save()

        self.assertTrue(revoke_fulfillment_for_refund(refund))
        self.assertEqual(refund.status, REFUND.PAYMENT_REFUNDED)
        self.assertEqual({line.status for line in refund.lines.all()}, {REFUND_LINE.COMPLETE})

    @override_settings(FULFILLMENT_MODULES=['ecommerce.extensions.fulfillment.tests.modules.RevocationFailureModule'])
    def test_revoke_fulfillment_for_refund_revocation_error(self):
        """
        Verify the function sets the status of RefundLines and the Refund to "Revocation Error" if revocation fails.
        """
        refund = RefundFactory(status=REFUND.PAYMENT_REFUNDED)
        self.assertFalse(revoke_fulfillment_for_refund(refund))
        self.assertEqual(refund.status, REFUND.PAYMENT_REFUNDED)
        self.assertEqual({line.status for line in refund.lines.all()}, {REFUND_LINE.REVOCATION_ERROR})
