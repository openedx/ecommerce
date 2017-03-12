from django.core.management import CommandError, call_command
from oscar.core.loading import get_model
from oscar.test import factories

from ecommerce.tests.testcases import TestCase

BasketLine = get_model('basket', 'Line')
Order = get_model('order', 'Order')
LinePrice = get_model('order', 'LinePrice')
PaymentEventQuantity = get_model('order', 'PaymentEventQuantity')
OrderNote = get_model('order', 'OrderNote')

LOGGER_NAME = 'ecommerce.extensions.order.management.commands.update_order'


class UpdateOrderCommandTests(TestCase):
    ORDER_NUMBER = "EDX-5266181"
    AMOUNT = 49.0

    def setUp(self):
        super(UpdateOrderCommandTests, self).setUp()
        self.correct_order = factories.create_order()
        self.affected_order = factories.create_order(number=self.ORDER_NUMBER)
        self.affected_order.total_incl_tax = 98.0
        self.affected_order.total_excl_tax = 98.0
        self.affected_order.save()
        LinePrice.objects.filter(order=self.affected_order).update(quantity=2)
        PaymentEventQuantity.objects.filter(line__in=self.affected_order.lines.all()).update(quantity=2)
        BasketLine.objects.filter(basket=self.affected_order.basket).update(quantity=2)

    def test_handle_invalid_order(self):
        """Verify that the command raises exception if order_number is not valid."""
        self.affected_order.delete()
        with self.assertRaises(CommandError):
            call_command('update_order')

    def test_handle(self):
        """ Verify the management command update the affected order."""

        self.assertEqual(OrderNote.objects.filter(order=self.affected_order).count(), 0)
        amount = 49
        call_command('update_order')

        affected_order = Order.objects.get(number=self.affected_order.number)
        correct_order = Order.objects.get(number=self.correct_order.number)
        # Verify that the command updated the prices of affected order.
        self.assertEqual(affected_order.total_incl_tax, amount)
        self.assertEqual(affected_order.total_excl_tax, amount)
        # Verify that the command did not updated the prices of other order.
        self.assertEqual(correct_order.total_incl_tax, self.correct_order.total_incl_tax)
        self.assertEqual(correct_order.total_excl_tax, self.correct_order.total_excl_tax)

        # Verify that the command updated the order lines.
        for line in affected_order.lines.all():
            self.assertEqual(line.quantity, 1)
            self.assertEqual(line.line_price_incl_tax, amount)
            self.assertEqual(line.line_price_excl_tax, amount)
            self.assertEqual(line.line_price_before_discounts_excl_tax, amount)
        correct_order_line = correct_order.lines.all()[0]
        correct_line_before_update = self.correct_order.lines.all()[0]
        # Verify that the command did not updated the other order lines.
        self.assertEqual(correct_order_line.quantity, correct_line_before_update.quantity)
        self.assertEqual(correct_order_line.line_price_incl_tax, correct_line_before_update.line_price_incl_tax)
        self.assertEqual(correct_order_line.line_price_excl_tax, correct_line_before_update.line_price_excl_tax)
        self.assertEqual(
            correct_order_line.line_price_before_discounts_excl_tax,
            correct_line_before_update.line_price_before_discounts_excl_tax
        )

        for line_price in LinePrice.objects.filter(order=self.affected_order).all():
            self.assertEqual(line_price.quantity, 1)

        self.assertEqual(OrderNote.objects.filter(order=self.affected_order).count(), 1)
        for basket_line in BasketLine.objects.filter(basket=self.affected_order.basket).all():
            self.assertEqual(basket_line.quantity, 1)

    def test_handle_order_without_basket(self):
        amount = 49
        basket_lines = BasketLine.objects.filter(basket=self.affected_order.basket).values("id")
        line_ids = [line_id["id"] for line_id in basket_lines]
        self.affected_order.basket = None
        self.affected_order.save()
        call_command(
            'update_order', order_number=self.affected_order.number, amount=amount
        )
        basket_lines = BasketLine.objects.filter(id__in=line_ids).all()
        for basket_line in basket_lines:
            self.assertEqual(basket_line.quantity, 2)
