from django.core.management import call_command
from oscar.test import factories

from ecommerce.invoice.models import Invoice
from ecommerce.tests.testcases import TestCase


class InvoiceTests(TestCase):
    """Test to ensure Invoice objects are created correctly"""
    def setUp(self):
        super(InvoiceTests, self).setUp()
        self.basket = factories.create_basket(empty=True)
        self.basket.owner = factories.UserFactory()
        self.basket.order = factories.OrderFactory()
        self.basket.save()
        self.invoice = Invoice.objects.create(order=self.basket.order, state='Paid')

    def test_order(self):
        """Test to check invoice order"""
        self.assertEqual(self.basket.order, self.invoice.order)

    def test_client(self):
        """Test to check invoice client"""
        self.assertEqual(self.basket.order.user, self.invoice.client)

    def test_total(self):
        """Test to check invoice total"""
        self.assertEqual(self.basket.order.total_incl_tax, self.invoice.total)


class InvoiceCommandTests(TestCase):
    """Tests for the squash_duplicate_invoices command."""

    def setUp(self):
        super(InvoiceCommandTests, self).setUp()
        coupon_pc = factories.ProductClassFactory(name='Coupon')
        self.product = factories.ProductFactory(product_class=coupon_pc)
        self.basket = factories.BasketFactory()
        self.basket.add_product(self.product, 1)
        self.order = factories.create_order(basket=self.basket)
        self.invoice = Invoice.objects.create(order=self.order)

    def assert_unique_invoice(self, product, invoice):
        """Helper method for asserting there is only one invoice for given product."""
        invoice_qs = Invoice.objects.filter(order__basket__lines__product=product)
        self.assertEqual(invoice_qs.count(), 1)
        self.assertEqual(invoice_qs.first(), invoice)

    def test_squashing_invoices(self):
        """Verify after calling the command the duplicate invoices are squashed."""
        Invoice.objects.create(order=self.order)
        self.assertEqual(Invoice.objects.filter(order__basket__lines__product=self.product).count(), 2)

        call_command('squash_duplicate_invoices')
        self.assert_unique_invoice(self.product, self.invoice)

    def test_not_squashing_invoices(self):
        """Verify the non-duplicate invoices are left the same."""
        self.assertEqual(Invoice.objects.filter(order__basket__lines__product=self.product).count(), 1)
        call_command('squash_duplicate_invoices')
        self.assert_unique_invoice(self.product, self.invoice)
