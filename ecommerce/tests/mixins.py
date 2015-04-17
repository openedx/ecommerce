# -*- coding: utf-8 -*-
"""Broadly-useful mixins for use in automated tests."""
import json
from decimal import Decimal as D

import jwt
from django.conf import settings
from django.core.cache import cache
from django.core.urlresolvers import reverse
from oscar.test import factories
from oscar.core.loading import get_model

from ecommerce.extensions.api.constants import APIConstants as AC
from ecommerce.extensions.fulfillment.mixins import FulfillmentMixin


Basket = get_model('basket', 'Basket')
ShippingEventType = get_model('order', 'ShippingEventType')
Order = get_model('order', 'Order')


class UserMixin(object):
    """Provides utility methods for creating and authenticating users in test cases."""
    password = 'test'

    def create_user(self, **kwargs):
        """Create a user, with overrideable defaults."""
        return factories.UserFactory(password=self.password, **kwargs)

    def generate_jwt_token_header(self, user, secret=None):
        """Generate a valid JWT token header for authenticated requests."""
        secret = secret or getattr(settings, 'JWT_AUTH')['JWT_SECRET_KEY']
        payload = {
            'username': user.username,
            'email': user.email,
        }
        return "JWT {token}".format(token=jwt.encode(payload, secret))


class ThrottlingMixin(object):
    """Provides utility methods for test cases validating the behavior of rate-limited endpoints."""
    def setUp(self):
        super(ThrottlingMixin, self).setUp()

        # Throttling for tests relies on the cache. To get around throttling, simply clear the cache.
        self.addCleanup(cache.clear)


class BasketCreationMixin(object):
    """Provides utility methods for creating baskets in test cases."""
    PATH = reverse('api:v2:baskets:create')
    SHIPPING_EVENT_NAME = FulfillmentMixin.SHIPPING_EVENT_NAME
    JWT_SECRET_KEY = getattr(settings, 'JWT_AUTH')['JWT_SECRET_KEY']
    FREE_SKU = u'𝑭𝑹𝑬𝑬-𝑷𝑹𝑶𝑫𝑼𝑪𝑻'
    USER_DATA = {
        'username': 'sgoodman',
        'email': 'saul@bettercallsaul.com',
    }

    def setUp(self):
        super(BasketCreationMixin, self).setUp()

        product_class = factories.ProductClassFactory(
            name=u'𝑨𝒖𝒕𝒐𝒎𝒐𝒃𝒊𝒍𝒆',
            requires_shipping=False,
            track_stock=False
        )
        self.base_product = factories.ProductFactory(
            structure='parent',
            title=u'𝑳𝒂𝒎𝒃𝒐𝒓𝒈𝒉𝒊𝒏𝒊 𝑮𝒂𝒍𝒍𝒂𝒓𝒅𝒐',
            product_class=product_class,
            stockrecords=None,
        )
        self.free_product = factories.ProductFactory(
            structure='child',
            parent=self.base_product,
            title=u'𝑪𝒂𝒓𝒅𝒃𝒐𝒂𝒓𝒅 𝑪𝒖𝒕𝒐𝒖𝒕',
            stockrecords__partner_sku=self.FREE_SKU,
            stockrecords__price_excl_tax=D('0.00'),
        )

    def generate_token(self, payload, secret=None):
        """Generate a JWT token with the provided payload."""
        secret = secret or self.JWT_SECRET_KEY
        token = jwt.encode(payload, secret)
        return token

    def create_basket(self, skus=None, checkout=None, payment_processor_name=None, auth=True, token=None):
        """Issue a POST request to the basket creation endpoint."""
        request_data = {}
        if skus:
            request_data[AC.KEYS.PRODUCTS] = []
            for sku in skus:
                request_data[AC.KEYS.PRODUCTS].append({AC.KEYS.SKU: sku})

        if checkout:
            request_data[AC.KEYS.CHECKOUT] = checkout

        if payment_processor_name:
            request_data[AC.KEYS.PAYMENT_PROCESSOR_NAME] = payment_processor_name

        if auth:
            token = token or self.generate_token(self.USER_DATA)
            response = self.client.post(
                self.PATH,
                data=json.dumps(request_data),
                content_type='application/json',
                HTTP_AUTHORIZATION='JWT ' + token
            )
        else:
            response = self.client.post(
                self.PATH,
                data=json.dumps(request_data),
                content_type='application/json'
            )

        return response

    def assert_successful_basket_creation(
            self, skus=None, checkout=None, payment_processor_name=None, requires_payment=False
    ):
        """Verify that basket creation succeeded."""
        # Ideally, we'd use Oscar's ShippingEventTypeFactory here, but it's not exposed/public.
        ShippingEventType.objects.create(name=self.SHIPPING_EVENT_NAME)

        response = self.create_basket(skus=skus, checkout=checkout, payment_processor_name=payment_processor_name)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], Basket.objects.get().id)

        if checkout:
            if requires_payment:
                self.assertIsNone(response.data[AC.KEYS.ORDER])
                self.assertIsNotNone(response.data[AC.KEYS.PAYMENT_DATA][AC.KEYS.PAYMENT_PROCESSOR_NAME])
                self.assertIsNotNone(response.data[AC.KEYS.PAYMENT_DATA][AC.KEYS.PAYMENT_FORM_DATA])
                self.assertIsNotNone(response.data[AC.KEYS.PAYMENT_DATA][AC.KEYS.PAYMENT_PAGE_URL])
            else:
                self.assertEqual(response.data[AC.KEYS.ORDER][AC.KEYS.ORDER_NUMBER], Order.objects.get().number)
                self.assertIsNone(response.data[AC.KEYS.PAYMENT_DATA])
        else:
            self.assertIsNone(response.data[AC.KEYS.ORDER])
            self.assertIsNone(response.data[AC.KEYS.PAYMENT_DATA])
