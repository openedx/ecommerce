

from oscar.test import factories

from ecommerce.extensions.test.factories import create_basket
from ecommerce.invoice.models import Invoice
from ecommerce.tests.factories import UserFactory
from ecommerce.tests.testcases import TestCase


class InvoiceTests(TestCase):
    """Test to ensure Invoice objects are created correctly"""
    def setUp(self):
        super(InvoiceTests, self).setUp()
        self.basket = create_basket(owner=UserFactory(), empty=True)
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
