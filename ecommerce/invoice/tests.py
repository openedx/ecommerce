from django.core.management import call_command
from oscar.core.loading import get_model
from oscar.test import factories

from ecommerce.core.models import BusinessClient
from ecommerce.invoice.models import Invoice
from ecommerce.tests.testcases import TestCase

Order = get_model('order', 'Order')


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


class PopulateInvoiceOrdersCommandTests(TestCase):
    """Tests for the populate_invoice_orders command."""

    def setUp(self):
        super(PopulateInvoiceOrdersCommandTests, self).setUp()
        self.order = factories.OrderFactory()
        self.basket = factories.BasketFactory()
        self.basket.owner = factories.UserFactory()
        self.basket.save()

    def test_order_populated(self):
        """Verify the order field is populated and basket set to None."""
        self.order.basket = self.basket
        self.order.save()
        invoice_before = Invoice.objects.create(basket=self.basket)
        self.assertIsNone(invoice_before.order)

        call_command('populate_invoice_orders')
        invoice_after = Invoice.objects.first()
        self.assertIsNone(invoice_after.basket)
        self.assertEqual(invoice_after.order, self.order)

    def test_non_existing_order(self):
        """Verify the invoice is not altered if no order exists."""
        self.assertIsNone(self.order.basket)
        invoice_before = Invoice.objects.create(basket=self.basket)
        invoice_before_no_basket = Invoice.objects.create()
        self.assertIsNone(invoice_before.order)
        self.assertIsNone(invoice_before_no_basket.order)

        call_command('populate_invoice_orders')
        invoices_after = Invoice.objects.all()
        self.assertEqual(invoices_after.count(), 2)
        self.assertIsNone(invoices_after.first().order)
        self.assertIsNone(invoices_after.last().order)
        self.assertEqual(invoices_after.get(id=invoice_before.id).basket, self.basket)

    def test_client_changed(self):
        """Verify the business client value is added if it doesn't exist."""
        self.assertIsNotNone(self.basket.owner)
        self.order.basket = self.basket
        self.order.save()
        invoice_before = Invoice.objects.create(basket=self.basket)
        self.assertIsNone(invoice_before.business_client)
        self.assertEqual(BusinessClient.objects.count(), 0)

        call_command('populate_invoice_orders')
        invoice_after = Invoice.objects.first()

        self.assertEqual(BusinessClient.objects.count(), 1)
        self.assertEqual(invoice_after.business_client, BusinessClient.objects.first())

    def test_client_unchanged(self):
        """Verify the business client value is unchanged if it exist."""
        self.order.basket = self.basket
        self.order.save()
        business_client = BusinessClient.objects.create(name='Tester')
        Invoice.objects.create(
            basket=self.basket,
            business_client=business_client
        )

        call_command('populate_invoice_orders')
        invoice_after = Invoice.objects.first()
        self.assertEqual(invoice_after.business_client, business_client)


class SquashDuplicateInvoicesCommandTests(TestCase):
    """Tests for the squash_duplicate_invoices command."""

    def setUp(self):
        super(SquashDuplicateInvoicesCommandTests, self).setUp()
        coupon_pc = factories.ProductClassFactory(name='Coupon')
        self.product = factories.ProductFactory(product_class=coupon_pc)
        self.basket = factories.BasketFactory()
        self.basket.add_product(self.product, 1)
        self.order = factories.create_order(basket=self.basket)
        self.invoice = Invoice.objects.create(order=self.order)

    def assert_unique_invoice(self, product, invoice):
        """Helper method for asserting there is only one invoice for given product."""
        invoice_qs = Invoice.objects.filter(order__lines__product=product)
        self.assertEqual(invoice_qs.count(), 1)
        self.assertEqual(invoice_qs.first(), invoice)

    def test_squashing_invoices(self):
        """Verify after calling the command the duplicate invoices are squashed."""
        Invoice.objects.create(order=self.order)
        self.assertEqual(Invoice.objects.filter(order__lines__product=self.product).count(), 2)

        call_command('squash_duplicate_invoices')
        self.assert_unique_invoice(self.product, self.invoice)

    def test_not_squashing_invoices(self):
        """Verify the non-duplicate invoices are left the same."""
        self.assertEqual(Invoice.objects.filter(order__lines__product=self.product).count(), 1)
        call_command('squash_duplicate_invoices')
        self.assert_unique_invoice(self.product, self.invoice)
