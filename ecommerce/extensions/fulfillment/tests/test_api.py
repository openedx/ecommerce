"""Tests for the Fulfillment API"""
# pylint: disable=abstract-method
import ddt
from nose.tools import raises
from django.test import TestCase
from django.test.utils import override_settings
from django.contrib.auth import get_user_model
from oscar.test import factories

from ecommerce.extensions.fulfillment.modules import FulfillmentModule
from ecommerce.extensions.fulfillment import api as fulfillment_api
from ecommerce.extensions.fulfillment import errors
from ecommerce.extensions.fulfillment.status import ORDER, LINE


class FakeFulfillmentModule(FulfillmentModule):
    """Fake Fulfillment Module used to test the API without specific implementations."""

    def get_supported_lines(self, order, lines):
        """Returns a list of lines this Fake module supposedly supports."""
        return lines

    def fulfill_product(self, order, lines):
        """Fulfill product. Mark all lines success."""
        for line in lines:
            line.set_status(LINE.COMPLETE)


class FulfillmentNothingModule(FulfillmentModule):
    """Fake Fulfillment Module that refuses to fulfill anything."""

    def get_supported_lines(self, order, lines):
        """Returns an empty list, because this module supports nothing."""
        return []


@ddt.ddt
class FulfillmentTest(TestCase):
    """
    Test course seat fulfillment.
    """

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username='Fry', email='fry@planetexpress.com', password='top_secret'
        )
        self.product_class = factories.ProductClassFactory(
            name='Seat', requires_shipping=False, track_stock=False
        )
        self.course = factories.ProductFactory(
            structure='parent', upc='001', title='EdX DemoX Course', product_class=self.product_class
        )
        self.seat = factories.ProductFactory(
            structure='child',
            upc='002',
            title='Seat in EdX DemoX Course with Honor Certificate',
            product_class=self.product_class,
            parent=self.course
        )
        for stock_record in self.seat.stockrecords.all():
            stock_record.price_currency = 'USD'
            stock_record.save()

        basket = factories.create_basket(empty=True)
        basket.add_product(self.seat, 1)
        self.order = factories.create_order(number=1, basket=basket, user=self.user)

        # Move the order from 'Open' to 'Paid' so fulfillment can be completed.
        self.order.set_status(ORDER.BEING_PROCESSED)
        self.order.set_status(ORDER.PAID)

    @override_settings(FULFILLMENT_MODULES=['ecommerce.extensions.fulfillment.tests.test_api.FakeFulfillmentModule', ])
    def test_seat_fulfillment(self):
        """Test a basic fulfillment of a Course Seat."""
        fulfillment_api.fulfill_order(self.order, self.order.lines)
        self.assertEquals(ORDER.COMPLETE, self.order.status)
        self.assertEquals(LINE.COMPLETE, self.order.lines.all()[0].status)

    @override_settings(FULFILLMENT_MODULES=['ecommerce.extensions.fulfillment.tests.test_api.FakeFulfillmentModule', ])
    @raises(errors.IncorrectOrderStatusError)
    def test_bad_fulfillment_state(self):
        """Test a basic fulfillment of a Course Seat."""
        # Set the order to Refunded, which cannot be fulfilled.
        self.order.set_status(ORDER.FULFILLMENT_ERROR)
        self.order.set_status(ORDER.REFUNDED)
        fulfillment_api.fulfill_order(self.order, self.order.lines)

    @override_settings(FULFILLMENT_MODULES=['ecommerce.extensions.fulfillment.tests.test_api.FulfillNothingModule', ])
    def test_unknown_product_type(self):
        """Test an incorrect Fulfillment Module."""
        fulfillment_api.fulfill_order(self.order, self.order.lines)
        self.assertEquals(ORDER.FULFILLMENT_ERROR, self.order.status)
        self.assertEquals(LINE.FULFILLMENT_CONFIGURATION_ERROR, self.order.lines.all()[0].status)

    @override_settings(FULFILLMENT_MODULES=['ecommerce.extensions.fulfillment.tests.test_api.NotARealModule', ])
    def test_incorrect_module(self):
        """Test an incorrect Fulfillment Module."""
        fulfillment_api.fulfill_order(self.order, self.order.lines)
        self.assertEquals(ORDER.FULFILLMENT_ERROR, self.order.status)
        self.assertEquals(LINE.FULFILLMENT_CONFIGURATION_ERROR, self.order.lines.all()[0].status)
