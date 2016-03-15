"""Test Order Utility classes """
import mock

from django.test.client import RequestFactory
from oscar.core.loading import get_class
from oscar.test.factories import create_basket as oscar_create_basket
from oscar.test.newfactories import BasketFactory

from ecommerce.extensions.fulfillment.status import ORDER
from ecommerce.tests.factories import SiteConfigurationFactory, PartnerFactory
from ecommerce.tests.testcases import TestCase

NoShippingRequired = get_class('shipping.methods', 'NoShippingRequired')
OrderCreator = get_class('order.utils', 'OrderCreator')
OrderNumberGenerator = get_class('order.utils', 'OrderNumberGenerator')
OrderTotalCalculator = get_class('checkout.calculators', 'OrderTotalCalculator')


class OrderNumberGeneratorTests(TestCase):
    generator = OrderNumberGenerator()

    def assert_order_number_matches_basket(self, basket, partner):
        expected = '{}-{}'.format(partner.short_code.upper(), 100000 + basket.id)
        self.assertEqual(self.generator.order_number(basket), expected)

    def test_order_number(self):
        """ Verify the method returns an order number determined using the basket's site/partner and ID. """
        basket = BasketFactory(site=self.site)
        self.assert_order_number_matches_basket(basket, self.partner)

    def test_order_number_for_basket_without_site(self):
        """ Verify the order number is linked to the default site, if the basket has no associated site. """
        site_configuration = SiteConfigurationFactory(site__domain='acme.fake', partner__name='ACME')
        site = site_configuration.site
        partner = site_configuration.partner
        basket = BasketFactory(site=None)

        request = RequestFactory().get('')
        request.session = None
        request.site = site

        with mock.patch('ecommerce.extensions.order.utils.get_current_request', mock.Mock(return_value=request)):
            self.assert_order_number_matches_basket(basket, partner)

    def test_order_number_from_basket_id(self):
        """ Verify the method returns an order number determined using the basket's ID, and the specified partner. """
        basket = BasketFactory()
        acme = PartnerFactory(name='ACME')

        for partner in (self.partner, acme,):
            self.assertEqual(self.generator.order_number_from_basket_id(partner, basket.id),
                             '{}-{}'.format(partner.short_code.upper(), 100000 + basket.id))

    def test_basket_id(self):
        """ Verify the method returns the ID of the basket associated with a given order number. """
        self.assertEqual(self.generator.basket_id('EDX-100001'), 1)
        self.assertEqual(self.generator.basket_id('ACME-101001'), 1001)


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
