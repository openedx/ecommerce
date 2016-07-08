from django.core.management import call_command
from oscar.core.loading import get_model
from oscar.test import factories
from testfixtures import LogCapture

from ecommerce.core.models import BusinessClient, Client
from ecommerce.coupons.tests.mixins import CouponMixin
from ecommerce.invoice.models import Invoice
from ecommerce.tests.testcases import TestCase

Basket = get_model('basket', 'Basket')
ProductClass = get_model('catalogue', 'ProductClass')


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


class InvoiceManagementCommandTests(CouponMixin, TestCase):
    """ Tests for the invoice management commands. """

    def setUp(self):
        super(InvoiceManagementCommandTests, self).setUp()
        self.product = factories.ProductFactory(product_class=ProductClass.objects.get(name='Coupon'))
        client = Client.objects.create(username='Tester')
        self.basket = factories.BasketFactory(owner=client)
        self.basket.add_product(self.product, 1)
        self.order = factories.create_order(basket=self.basket)

    def test_invoice_created(self):
        """ Verify a new invoice is created for an order that does not have it. """
        self.assertEqual(Invoice.objects.count(), 0)
        call_command('create_invoices')
        self.assertEqual(Invoice.objects.count(), 1)

        invoice = Invoice.objects.first()
        self.assertEqual(invoice.order, self.order)
        self.assertEqual(invoice.business_client.name, self.basket.owner.username)

    def test_invoice_not_created(self):
        """ Verify no new invoices are created when orders already have invoices. """
        business_client = BusinessClient.objects.create(name='Tester')
        Invoice.objects.create(order=self.order, business_client=business_client)
        self.assertEqual(Invoice.objects.count(), 1)
        call_command('create_invoices')
        self.assertEqual(Invoice.objects.count(), 1)


class InvoiceManagementCommandExceptionsTest(CouponMixin, TestCase):
    """ Moved to this new test class because of a segmentation error. """

    def setUp(self):
        super(InvoiceManagementCommandExceptionsTest, self).setUp()
        self.product = factories.ProductFactory(product_class=ProductClass.objects.get(name='Coupon'))
        self.basket = factories.BasketFactory()
        self.basket.add_product(self.product, 1)
        self.basket.submit()

    def assert_log_message(self, msg):
        logger_name = 'ecommerce.invoice.management.commands.create_invoices'
        with LogCapture(logger_name) as l:
            call_command('create_invoices')
            l.check((logger_name, 'ERROR', msg))

    def test_command_basket_exception(self):
        Basket.objects.all().delete()
        self.assert_log_message('Basket for coupon {} does not exist!'.format(self.product.id))

    def test_command_order_exception(self):
        self.assert_log_message('Order for basket {} does not exist!'.format(self.basket.id))
