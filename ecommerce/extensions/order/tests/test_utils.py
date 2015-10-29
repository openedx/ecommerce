"""Test Order Utility classes """
from django.test import override_settings
from oscar.core.loading import get_class
from oscar.test.factories import create_basket as oscar_create_basket
from oscar.test.newfactories import BasketFactory

from ecommerce.extensions.fulfillment.status import ORDER
from ecommerce.tests.factories import SiteConfigurationFactory
from ecommerce.tests.testcases import TestCase

NoShippingRequired = get_class('shipping.methods', 'NoShippingRequired')
OrderCreator = get_class('order.utils', 'OrderCreator')
OrderNumberGenerator = get_class('order.utils', 'OrderNumberGenerator')
OrderTotalCalculator = get_class('checkout.calculators', 'OrderTotalCalculator')


class UtilsTest(TestCase):
    """Unit tests for the order utility functions and classes. """

    ORDER_NUMBER_PREFIX = 'FOO'

    @override_settings(ORDER_NUMBER_PREFIX=ORDER_NUMBER_PREFIX)
    def test_order_number_generation(self):
        """
        Verify that order numbers are generated correctly, and that they can
        be converted back into basket IDs when necessary.
        """
        first_basket = BasketFactory()
        second_basket = BasketFactory()

        first_order_number = OrderNumberGenerator().order_number(first_basket)
        second_order_number = OrderNumberGenerator().order_number(second_basket)

        self.assertIn(self.ORDER_NUMBER_PREFIX, first_order_number)
        self.assertIn(self.ORDER_NUMBER_PREFIX, second_order_number)
        self.assertNotEqual(first_order_number, second_order_number)

        first_basket_id = OrderNumberGenerator().basket_id(first_order_number)
        second_basket_id = OrderNumberGenerator().basket_id(second_order_number)

        self.assertEqual(first_basket_id, first_basket.id)
        self.assertEqual(second_basket_id, second_basket.id)


class OrderCreatorTests(TestCase):
    order_creator = OrderCreator()

    def setUp(self):
        super(OrderCreatorTests, self).setUp()
        self.user = self.create_user()

    def create_order_model(self, basket):
        """ Call the create_order_model method to create an Order from the given Basket. """
        shipping_method = NoShippingRequired()
        shipping_charge = shipping_method.calculate(basket)
        total = OrderTotalCalculator().calculate(basket, shipping_charge)
        return self.order_creator.create_order_model(self.user, basket, None, shipping_method, shipping_charge,
                                                     None, total, basket.order_number, ORDER.OPEN)

    def create_basket(self, site):
        """ Returns a new Basket with the specified Site. """
        basket = oscar_create_basket()
        basket.site = site
        basket.save()
        return basket

    def test_create_order_model_default_site(self):
        """
        Verify the create_order_model method associates the order with the default site
        if the basket does not have a site set.
        """
        # Create a basket without a site
        basket = self.create_basket(None)

        # Ensure the order's site is set to the default site
        order = self.create_order_model(basket)
        self.assertEqual(order.site, self.site)

    def test_create_order_model_basket_site(self):
        """ Verify the create_order_model method associates the order with the basket's site. """
        # Create a non-default site
        site_configuration = SiteConfigurationFactory(site__domain='star.fake', partner__name='star')
        site = site_configuration.site

        # Associate the basket with the non-default site
        basket = self.create_basket(site)

        # Ensure the order has the non-default site
        order = self.create_order_model(basket)
        self.assertEqual(order.site, site)
