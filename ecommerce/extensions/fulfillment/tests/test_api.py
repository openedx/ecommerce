"""Tests for the Fulfillment API"""
import ddt
from django.test import TestCase
from django.test.utils import override_settings
from nose.tools import raises

from ecommerce.extensions.fulfillment import api, exceptions
from ecommerce.extensions.fulfillment.status import ORDER, LINE
from ecommerce.extensions.fulfillment.tests.mixins import FulfillmentTestMixin


@ddt.ddt
class FulfillmentTest(FulfillmentTestMixin, TestCase):
    """
    Test course seat fulfillment.
    """

    def setUp(self):
        super(FulfillmentTest, self).setUp()
        self.order = self.generate_open_order()

    @override_settings(FULFILLMENT_MODULES=['ecommerce.extensions.fulfillment.tests.modules.FakeFulfillmentModule', ])
    def test_successful_fulfillment(self):
        """ Test a successful fulfillment of an order. """
        api.fulfill_order(self.order, self.order.lines)
        self.assert_order_fulfilled(self.order)

    @override_settings(FULFILLMENT_MODULES=['ecommerce.extensions.fulfillment.tests.modules.FakeFulfillmentModule', ])
    @raises(exceptions.IncorrectOrderStatusError)
    def test_bad_fulfillment_state(self):
        """Test a basic fulfillment of a Course Seat."""
        # Set the order to Refunded, which cannot be fulfilled.
        self.order.set_status(ORDER.COMPLETE)
        api.fulfill_order(self.order, self.order.lines)

    @override_settings(FULFILLMENT_MODULES=['ecommerce.extensions.fulfillment.tests.modules.FulfillNothingModule', ])
    def test_unknown_product_type(self):
        """Test an incorrect Fulfillment Module."""
        api.fulfill_order(self.order, self.order.lines)
        self.assertEquals(ORDER.FULFILLMENT_ERROR, self.order.status)
        self.assertEquals(LINE.FULFILLMENT_CONFIGURATION_ERROR, self.order.lines.all()[0].status)

    @override_settings(FULFILLMENT_MODULES=['ecommerce.extensions.fulfillment.tests.modules.NotARealModule', ])
    def test_incorrect_module(self):
        """Test an incorrect Fulfillment Module."""
        api.fulfill_order(self.order, self.order.lines)
        self.assertEquals(ORDER.FULFILLMENT_ERROR, self.order.status)
        self.assertEquals(LINE.FULFILLMENT_CONFIGURATION_ERROR, self.order.lines.all()[0].status)
