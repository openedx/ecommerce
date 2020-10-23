"""Test Order Utility classes """


import datetime
import json
import logging

import ddt
import httpretty
import mock
import pytz
from django.test.client import RequestFactory
from edx_django_utils.cache import TieredCache
from oscar.core.loading import get_class, get_model
from oscar.test.factories import BasketFactory
from requests import Timeout
from testfixtures import LogCapture

from ecommerce.core.url_utils import get_lms_entitlement_api_url
from ecommerce.extensions.fulfillment.status import ORDER
from ecommerce.extensions.order.utils import UserAlreadyPlacedOrder
from ecommerce.extensions.refund.tests.factories import RefundFactory
from ecommerce.extensions.refund.tests.mixins import RefundTestMixin
from ecommerce.extensions.test.factories import create_basket, create_order
from ecommerce.referrals.models import Referral
from ecommerce.tests.factories import PartnerFactory, SiteConfigurationFactory
from ecommerce.tests.testcases import TestCase

LOGGER_NAME = 'ecommerce.extensions.order.utils'
EXPIRED_DATE = datetime.datetime(year=1985, month=10, day=26, hour=1, minute=20, tzinfo=pytz.utc)

Country = get_class('address.models', 'Country')
NoShippingRequired = get_class('shipping.methods', 'NoShippingRequired')
Option = get_model('catalogue', 'Option')
OrderCreator = get_class('order.utils', 'OrderCreator')
OrderNumberGenerator = get_class('order.utils', 'OrderNumberGenerator')
OrderTotalCalculator = get_class('checkout.calculators', 'OrderTotalCalculator')
OrderLine = get_model('order', 'Line')
RefundLine = get_model('refund', 'RefundLine')
ShippingAddress = get_class('order.models', 'ShippingAddress')


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
        self.country = Country.objects.create(printable_name='Fake', name='fake')
        self.shipping_address = ShippingAddress.objects.create(line1='Fake Address', country=self.country)

    def create_order_model(self, basket):
        """ Call the create_order_model method to create an Order from the given Basket. """
        shipping_method = NoShippingRequired()
        shipping_charge = shipping_method.calculate(basket)
        total = OrderTotalCalculator().calculate(basket, shipping_charge)
        return self.order_creator.create_order_model(
            self.user, basket,
            self.shipping_address,
            shipping_method,
            shipping_charge,
            None,
            total,
            basket.order_number,
            ORDER.OPEN,
            currency='fake'
        )

    def create_basket(self, site):
        """ Returns a new Basket with the specified Site. """
        basket = create_basket()
        basket.site = site
        basket.save()
        return basket

    def create_referral(self, basket, affiliate_id):
        """ Returns a new Referral associated with the specified basket. """
        return Referral.objects.create(basket=basket, affiliate_id=affiliate_id, site=basket.site)

    def test_create_order_model_default_site_and_partner(self):
        """
        Verify the create_order_model method associates the order with the default site and it's partner
        if the basket does not have a site set.
        """
        # Create a basket without a site
        basket = self.create_basket(None)

        # Ensure the order's site and partner is set to the default site and partner
        order = self.create_order_model(basket)
        self.assertEqual(order.site, self.site)
        self.assertEqual(order.partner, self.partner)

    def test_create_order_model_basket_site(self):
        """ Verify the create_order_model method associates the order with the basket's site. """
        # Create a non-default site
        site_configuration = SiteConfigurationFactory(site__domain='star.fake', partner__name='star')
        site = site_configuration.site

        # Associate the basket with the non-default site
        basket = self.create_basket(site)

        # Ensure the order has the non-default site and partner
        order = self.create_order_model(basket)
        self.assertEqual(order.site, site)
        self.assertEqual(order.partner, site_configuration.partner)

    def test_create_order_model_basket_referral(self):
        """ Verify the create_order_model method associates the order with the basket's site. """
        site_configuration = SiteConfigurationFactory(site__domain='star.fake', partner__name='star')
        site = site_configuration.site
        affiliate_id = 'test affiliate'

        # Create the basket and associated referral
        basket = self.create_basket(site)
        self.create_referral(basket, affiliate_id)

        # Ensure the referral is now associated with the order and has the correct affiliate id
        order = self.create_order_model(basket)
        referral = Referral.objects.get(order_id=order.id)
        self.assertEqual(referral.affiliate_id, affiliate_id)

    def test_create_order_model_basket_no_referral(self):
        """ Verify the create_order_model method logs error if no referral."""
        # Create a site config to clean up log messages
        site_configuration = SiteConfigurationFactory(site__domain='star.fake', partner__name='star')
        site = site_configuration.site
        # Create the basket WITHOUT an associated referral
        basket = self.create_basket(site)

        with LogCapture(LOGGER_NAME, level=logging.DEBUG) as logger:
            order = self.create_order_model(basket)
            message = 'Order [{order_id}] has no referral associated with its basket.'.format(order_id=order.id)
            logger.check((LOGGER_NAME, 'DEBUG', message))

    def test_create_order_model_basket_referral_error(self):
        """ Verify the create_order_model method logs error for referral errors. """
        # Create a site config to clean up log messages
        site_configuration = SiteConfigurationFactory(site__domain='star.fake', partner__name='star')
        site = site_configuration.site
        # Create the basket WITHOUT an associated referral
        basket = self.create_basket(site)

        with LogCapture(LOGGER_NAME, level=logging.ERROR) as logger:
            with mock.patch.object(Referral.objects, 'get', side_effect=Exception):
                order = self.create_order_model(basket)
                message = 'Referral for Order [{order_id}] failed to save.'.format(order_id=order.id)
                logger.check((LOGGER_NAME, 'ERROR', message))


@ddt.ddt
class UserAlreadyPlacedOrderTests(RefundTestMixin, TestCase):
    """
    Tests for Util class UserAlreadyPlacedOrder
    """
    def setUp(self):
        super(UserAlreadyPlacedOrderTests, self).setUp()
        self.user = self.create_user()
        self.order = create_order(site=self.site, user=self.user)
        self.product = self.get_order_product()
        self.entitlement_order = self.create_order(entitlement=True, user=self.user)
        line = self.entitlement_order.lines.first()
        self.entitlement_option = Option.objects.get(name='Course Entitlement')
        self.course_entitlement = line.product
        self.course_entitlement_uuid = line.attributes.get(option=self.entitlement_option).value

    def get_order_product(self, order=None):
        """
        Args:
            order: if no order given uses self.order
        Returns:
            the product order was placed for
        """
        order = self.order if not order else order
        return OrderLine.objects.get(order=order).product

    def test_already_have_not_refunded_order(self):
        """
        Test the case that user have a non refunded order for the product.
        """
        self.assertTrue(UserAlreadyPlacedOrder.user_already_placed_order(user=self.user, product=self.product,
                                                                         site=self.site))

    @httpretty.activate
    def test_already_have_not_refunded_entitlement_order(self):
        """
        Test the case that user has a non refunded order for the course entitlement
        """
        self.mock_access_token_response()
        body = {
            "user": "edx",
            "uuid": "adfca7da-e593-428b-b12d-f728e2dd220d",
            "course_uuid": "b084097a-7596-4fe6-b6a2-d335bffeb3f1",
            "expired_at": "2017-12-16T21:36:19.279647Z",
            "created": "2017-12-16T21:35:59.402622Z",
            "modified": "2017-12-16T21:36:19.280197Z",
            "mode": "verified",
            "order_number": "EDX-100014"
        }
        httpretty.register_uri(httpretty.GET, get_lms_entitlement_api_url() +
                               'entitlements/' + self.course_entitlement_uuid + '/',
                               status=200, body=json.dumps(body), content_type='application/json')
        self.assertFalse(UserAlreadyPlacedOrder.user_already_placed_order(user=self.user,
                                                                          product=self.course_entitlement,
                                                                          site=self.site))

    @httpretty.activate
    def test_already_expired_entitlement_order(self):
        """
        Test the case that user has a non refunded order for the course entitlement
        """
        self.mock_access_token_response()
        body = {
            "user": "edx",
            "uuid": "adfca7da-e593-428b-b12d-f728e2dd220d",
            "course_uuid": "b084097a-7596-4fe6-b6a2-d335bffeb3f1",
            "expired_at": None,
            "created": "2017-12-16T21:35:59.402622Z",
            "modified": "2017-12-16T21:36:19.280197Z",
            "mode": "verified",
            "order_number": "EDX-100014"
        }
        httpretty.register_uri(httpretty.GET, get_lms_entitlement_api_url() +
                               'entitlements/' + self.course_entitlement_uuid + '/',
                               status=200, body=json.dumps(body), content_type='application/json')
        self.assertTrue(UserAlreadyPlacedOrder.user_already_placed_order(user=self.user,
                                                                         product=self.course_entitlement,
                                                                         site=self.site))

    @httpretty.activate
    def test_refunded_entitlement_order_connection_timeout(self):
        """
        Test the case that we get an error trying to get the entitlement from LMS
        """
        httpretty.register_uri(httpretty.GET, get_lms_entitlement_api_url() +
                               'entitlements/' + self.course_entitlement_uuid + '/',
                               status=200, body={}, content_type='application/json',
                               side_effect=Timeout)

        self.assertFalse(UserAlreadyPlacedOrder.user_already_placed_order(user=self.user,
                                                                          product=self.course_entitlement,
                                                                          site=self.site))

    def test_no_previous_order(self):
        """
        Test the case that user do not have any previous order for the product.
        """
        user = self.create_user()
        self.assertFalse(UserAlreadyPlacedOrder.user_already_placed_order(user=user, product=self.product,
                                                                          site=self.site))

        self.assertFalse(UserAlreadyPlacedOrder.user_already_placed_order(user=user, product=self.course_entitlement,
                                                                          site=self.site))

    def test_already_have_refunded_order(self):
        """
        Test the case that user have a refunded order for the product.
        """
        user = self.create_user()
        refund = RefundFactory(user=user)
        refund_line = RefundLine.objects.get(refund=refund)
        refund_line.status = 'Complete'
        refund_line.save()
        product = self.get_order_product(order=refund.order)
        self.assertFalse(UserAlreadyPlacedOrder.user_already_placed_order(user=user, product=product, site=self.site))

    @ddt.data(('Open', False), ('Revocation Error', False), ('Denied', False), ('Complete', True))
    @ddt.unpack
    def test_is_order_line_refunded(self, refund_line_status, is_refunded):
        """
        Tests the functionality of is_order_line_refunded method.
        """
        user = self.create_user()
        refund = RefundFactory(user=user)
        refund_line = RefundLine.objects.get(refund=refund)
        refund_line.status = refund_line_status
        refund_line.save()
        self.assertEqual(UserAlreadyPlacedOrder.is_order_line_refunded(refund_line.order_line), is_refunded)

    @httpretty.activate
    def test_is_entitlement_expired_cached(self):
        """
        Test that entitlement's expired status gets cached

        We expect 2 calls to set_all_tiers in the is_entitlement_expired
        method due to:
            - the site_configuration api setup
            - the result being cached
        """
        self.mock_access_token_response()

        self.course_entitlement.expires = EXPIRED_DATE
        httpretty.register_uri(httpretty.GET, get_lms_entitlement_api_url() +
                               'entitlements/' + self.course_entitlement_uuid + '/',
                               status=200, body=json.dumps({}), content_type='application/json')

        with mock.patch.object(TieredCache, 'set_all_tiers', wraps=TieredCache.set_all_tiers) as mocked_set_all_tiers:
            mocked_set_all_tiers.assert_not_called()

            _ = UserAlreadyPlacedOrder.is_entitlement_expired(self.course_entitlement_uuid, site=self.site)
            self.assertEqual(mocked_set_all_tiers.call_count, 2)

            _ = UserAlreadyPlacedOrder.is_entitlement_expired(self.course_entitlement_uuid, site=self.site)
            self.assertEqual(mocked_set_all_tiers.call_count, 2)
