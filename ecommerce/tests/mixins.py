# -*- coding: utf-8 -*-
"""Broadly-useful mixins for use in automated tests."""
import json
from decimal import Decimal as D

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.urlresolvers import reverse
from mock import patch
from oscar.test import factories
from oscar.core.loading import get_model, get_class

from ecommerce.courses.utils import mode_for_seat
from ecommerce.extensions.api.constants import APIConstants as AC
from ecommerce.extensions.fulfillment.signals import SHIPPING_EVENT_NAME


Basket = get_model('basket', 'Basket')
Selector = get_class('partner.strategy', 'Selector')
ShippingEventType = get_model('order', 'ShippingEventType')
Order = get_model('order', 'Order')
User = get_user_model()


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


class JwtMixin(object):
    """ Mixin with JWT-related helper functions. """
    JWT_SECRET_KEY = getattr(settings, 'JWT_AUTH')['JWT_SECRET_KEY']

    def generate_token(self, payload, secret=None):
        """Generate a JWT token with the provided payload."""
        secret = secret or self.JWT_SECRET_KEY
        token = jwt.encode(payload, secret)
        return token


class BasketCreationMixin(JwtMixin):
    """Provides utility methods for creating baskets in test cases."""
    PATH = reverse('api:v2:baskets:create')
    FREE_SKU = u'𝑭𝑹𝑬𝑬-𝑷𝑹𝑶𝑫𝑼𝑪𝑻'
    USERNAME = 'sgoodman'
    USER_DATA = {
        'username': USERNAME,
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
        ShippingEventType.objects.get_or_create(name=SHIPPING_EVENT_NAME)

        with patch('ecommerce.extensions.analytics.utils.audit_log') as mock_audit_log:
            response = self.create_basket(skus=skus, checkout=checkout, payment_processor_name=payment_processor_name)

            self.assertEqual(response.status_code, 200)

            basket = Basket.objects.get()
            user = User.objects.get(username=self.USER_DATA['username'])
            basket.strategy = Selector().strategy(user=user)
            self.assertEqual(response.data['id'], basket.id)

            if checkout:
                self.assertTrue(mock_audit_log.called_with(
                    'basket_frozen',
                    amount=basket.total_excl_tax,
                    basket_id=basket.id,
                    currency=basket.currency,
                    user_id=basket.owner.id
                ))

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


class BusinessIntelligenceMixin(object):
    """Provides assertions for test cases validating the emission of business intelligence events."""

    def assert_correct_event(
            self, mock_track, instance, expected_user_id, expected_client_id, order_number, currency, total
    ):
        """Check that the tracking context was correctly reflected in the emitted event."""
        (event_user_id, event_name, event_payload), kwargs = mock_track.call_args
        self.assertEqual(event_user_id, expected_user_id)
        self.assertEqual(event_name, 'Completed Order')
        self.assertEqual(kwargs['context'], {'Google Analytics': {'clientId': expected_client_id}})
        self.assert_correct_event_payload(instance, event_payload, order_number, currency, total)

    def assert_correct_event_payload(self, instance, event_payload, order_number, currency, total):
        """
        Check that field values in the event payload correctly represent the
        completed order or refund.
        """
        self.assertEqual(['currency', 'orderId', 'products', 'total'], sorted(event_payload.keys()))
        self.assertEqual(event_payload['orderId'], order_number)
        self.assertEqual(event_payload['currency'], currency)

        lines = instance.lines.all()
        self.assertEqual(len(lines), len(event_payload['products']))

        model_name = instance.__class__.__name__
        tracked_products_dict = {product['id']: product for product in event_payload['products']}

        if model_name == 'Order':
            self.assertEqual(event_payload['total'], str(total))

            for line in lines:
                tracked_product = tracked_products_dict.get(line.partner_sku)
                self.assertIsNotNone(tracked_product)
                self.assertEqual(line.product.course.id, tracked_product['name'])
                self.assertEqual(str(line.line_price_excl_tax), tracked_product['price'])
                self.assertEqual(line.quantity, tracked_product['quantity'])
                self.assertEqual(mode_for_seat(line.product), tracked_product['sku'])
                self.assertEqual(line.product.get_product_class().name, tracked_product['category'])
        elif model_name == 'Refund':
            self.assertEqual(event_payload['total'], '-{}'.format(total))

            for line in lines:
                tracked_product = tracked_products_dict.get(line.order_line.partner_sku)
                self.assertIsNotNone(tracked_product)
                self.assertEqual(line.order_line.product.course.id, tracked_product['name'])
                self.assertEqual(str(line.line_credit_excl_tax), tracked_product['price'])
                self.assertEqual(-1 * line.quantity, tracked_product['quantity'])
                self.assertEqual(mode_for_seat(line.order_line.product), tracked_product['sku'])
                self.assertEqual(line.order_line.product.get_product_class().name, tracked_product['category'])
        else:
            # Payload validation is currently limited to order and refund events
            self.fail()
