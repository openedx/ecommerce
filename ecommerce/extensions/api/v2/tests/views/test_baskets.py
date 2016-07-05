# -*- coding: utf-8 -*-
from collections import namedtuple
from decimal import Decimal
import json

import ddt
from django.contrib.auth import get_user_model
from django.core.urlresolvers import reverse
from django.test import override_settings
import mock
from oscar.core.loading import get_model
from oscar.test import factories
from oscar.test.factories import BasketFactory
from rest_framework.throttling import UserRateThrottle

from ecommerce.extensions.api import exceptions as api_exceptions
from ecommerce.extensions.api.v2.tests.views import OrderDetailViewTestMixin, JSON_CONTENT_TYPE
from ecommerce.extensions.api.v2.views.baskets import BasketCreateView
from ecommerce.extensions.payment import exceptions as payment_exceptions
from ecommerce.extensions.payment.processors.cybersource import Cybersource
from ecommerce.tests.mixins import ThrottlingMixin, BasketCreationMixin
from ecommerce.tests.testcases import TestCase, TransactionTestCase

Basket = get_model('basket', 'Basket')
Order = get_model('order', 'Order')
ShippingEventType = get_model('order', 'ShippingEventType')
Refund = get_model('refund', 'Refund')
User = get_user_model()

LOGGER_NAME = 'ecommerce.extensions.api.v2.views.baskets'


@ddt.ddt
@override_settings(
    FULFILLMENT_MODULES=['ecommerce.extensions.fulfillment.tests.modules.FakeFulfillmentModule']
)
# Why TransactionTestCase? See http://stackoverflow.com/a/23326971.
class BasketCreateViewTests(BasketCreationMixin, ThrottlingMixin, TransactionTestCase):
    FREE_SKU = u'𝑭𝑹𝑬𝑬-𝑷𝑹𝑶𝑫𝑼𝑪𝑻'
    PAID_SKU = u'𝑷𝑨𝑰𝑫-𝑷𝑹𝑶𝑫𝑼𝑪𝑻'
    ALTERNATE_FREE_SKU = u'𝑨𝑳𝑻𝑬𝑹𝑵𝑨𝑻𝑬-𝑭𝑹𝑬𝑬-𝑷𝑹𝑶𝑫𝑼𝑪𝑻'
    ALTERNATE_PAID_SKU = u'𝑨𝑳𝑻𝑬𝑹𝑵𝑨𝑻𝑬-𝑷𝑨𝑰𝑫-𝑷𝑹𝑶𝑫𝑼𝑪𝑻'
    BAD_SKU = 'not-a-sku'
    UNAVAILABLE = False
    UNAVAILABLE_MESSAGE = 'Unavailable'
    FAKE_PROCESSOR_NAME = 'awesome-processor'

    def setUp(self):
        super(BasketCreateViewTests, self).setUp()

        self.paid_product = factories.ProductFactory(
            structure='child',
            parent=self.base_product,
            title=u'𝐋𝐏 𝟓𝟔𝟎-𝟒',
            stockrecords__partner_sku=self.PAID_SKU,
            stockrecords__price_excl_tax=Decimal('180000.00'),
            stockrecords__partner__short_code='oscr',
        )
        factories.ProductFactory(
            structure='child',
            parent=self.base_product,
            title=u'Papier-mâché',
            stockrecords__partner_sku=self.ALTERNATE_FREE_SKU,
            stockrecords__price_excl_tax=Decimal('0.00'),
            stockrecords__partner__short_code='otto',
        )
        factories.ProductFactory(
            structure='child',
            parent=self.base_product,
            title=u'𝐋𝐏 𝟓𝟕𝟎-𝟒 𝐒𝐮𝐩𝐞𝐫𝐥𝐞𝐠𝐠𝐞𝐫𝐚',
            stockrecords__partner_sku=self.ALTERNATE_PAID_SKU,
            stockrecords__price_excl_tax=Decimal('240000.00'),
            stockrecords__partner__short_code='dummy',
        )

    @ddt.data(
        ([FREE_SKU], False, None, False),
        ([FREE_SKU], True, None, False),
        ([FREE_SKU, ALTERNATE_FREE_SKU], True, None, False),
        ([PAID_SKU], False, None, True),
        ([PAID_SKU], True, None, True),
        ([PAID_SKU], True, Cybersource.NAME, True),
        ([PAID_SKU, ALTERNATE_PAID_SKU], True, None, True),
        ([FREE_SKU, PAID_SKU], True, None, True),
    )
    @ddt.unpack
    def test_basket_creation_and_checkout(self, skus, checkout, payment_processor_name, requires_payment):
        """Test that a variety of product combinations can be added to the basket and purchased."""
        self.assert_successful_basket_creation(skus, checkout, payment_processor_name, requires_payment)

    def test_multiple_baskets(self):
        """ Test that basket operations succeed if the user has editable baskets. The endpoint should
        ALWAYS create a new basket. """
        # Create two editable baskets for the user
        basket_count = 2
        for _ in xrange(basket_count):
            basket = Basket(owner=self.user, status='Open')
            basket.save()

        self.assertEqual(self.user.baskets.count(), basket_count)
        response = self.create_basket(skus=[self.PAID_SKU], checkout=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user.baskets.count(), basket_count + 1)

    @mock.patch('oscar.apps.partner.strategy.Structured.fetch_for_product')
    def test_order_unavailable_product(self, mock_fetch_for_product):
        """Test that requests for unavailable products fail with appropriate messaging."""
        OrderInfo = namedtuple('OrderInfo', 'availability')
        Availability = namedtuple('Availability', ['is_available_to_buy', 'message'])

        order_info = OrderInfo(Availability(self.UNAVAILABLE, self.UNAVAILABLE_MESSAGE))
        mock_fetch_for_product.return_value = order_info

        response = self.create_basket(skus=[self.PAID_SKU])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            self._bad_request_dict(
                api_exceptions.PRODUCT_UNAVAILABLE_DEVELOPER_MESSAGE.format(
                    sku=self.PAID_SKU,
                    availability=self.UNAVAILABLE_MESSAGE
                ),
                api_exceptions.PRODUCT_UNAVAILABLE_USER_MESSAGE
            )
        )

    def test_product_objects_missing(self):
        """Test that requests without at least one product object fail with appropriate messaging."""
        response = self.create_basket()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            self._bad_request_dict(
                api_exceptions.PRODUCT_OBJECTS_MISSING_DEVELOPER_MESSAGE,
                api_exceptions.PRODUCT_OBJECTS_MISSING_USER_MESSAGE
            )
        )

    def test_sku_missing(self):
        """Test that requests without a SKU fail with appropriate messaging."""
        request_data = {'products': [{'not-sku': 'foo'}]}
        response = self.client.post(
            self.PATH,
            data=json.dumps(request_data),
            content_type=JSON_CONTENT_TYPE,
            HTTP_AUTHORIZATION=self.generate_jwt_token_header(self.user)
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            self._bad_request_dict(
                api_exceptions.SKU_NOT_FOUND_DEVELOPER_MESSAGE,
                api_exceptions.SKU_NOT_FOUND_USER_MESSAGE
            )
        )

    def test_no_product_for_sku(self):
        """Test that requests for non-existent products fail with appropriate messaging."""
        response = self.create_basket(skus=[self.BAD_SKU])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            self._bad_request_dict(
                api_exceptions.PRODUCT_NOT_FOUND_DEVELOPER_MESSAGE.format(sku=self.BAD_SKU),
                api_exceptions.PRODUCT_NOT_FOUND_USER_MESSAGE
            )
        )

    def test_no_payment_processor(self):
        """Test that requests for handling payment with a non-existent processor fail."""
        response = self.create_basket(
            skus=[self.PAID_SKU],
            checkout=True,
            payment_processor_name=self.FAKE_PROCESSOR_NAME
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            self._bad_request_dict(
                payment_exceptions.PROCESSOR_NOT_FOUND_DEVELOPER_MESSAGE.format(name=self.FAKE_PROCESSOR_NAME),
                payment_exceptions.PROCESSOR_NOT_FOUND_USER_MESSAGE
            )
        )

    def test_throttling(self):
        """Test that the rate of requests to the basket creation endpoint is throttled."""
        request_limit = UserRateThrottle().num_requests
        # Make a number of requests equal to the number of allowed requests
        for _ in xrange(request_limit):
            self.create_basket(skus=[self.PAID_SKU])

        # Make one more request to trigger throttling of the client
        response = self.create_basket(skus=[self.PAID_SKU])
        self.assertEqual(response.status_code, 429)
        self.assertIn("Request was throttled.", response.data['detail'])

    def test_jwt_authentication(self):
        """Test that requests made without a valid JWT fail."""
        # Verify that the basket creation endpoint requires JWT authentication
        response = self.create_basket(skus=[self.PAID_SKU], auth=False)
        self.assertEqual(response.status_code, 401)

        # Verify that the basket creation endpoint requires valid user data in the JWT payload
        token = self.generate_token({})
        response = self.create_basket(skus=[self.PAID_SKU], token=token)
        self.assertEqual(response.status_code, 401)

        # Verify that the basket creation endpoint requires user data to be signed with a valid secret;
        # guarantee an invalid secret by truncating the valid secret
        invalid_secret = self.JWT_SECRET_KEY[:-1]
        payload = {
            'username': self.user.username,
            'email': self.user.email,
        }
        token = self.generate_token(payload, secret=invalid_secret)
        response = self.create_basket(skus=[self.PAID_SKU], token=token)
        self.assertEqual(response.status_code, 401)

    def _bad_request_dict(self, developer_message, user_message):
        bad_request_dict = {
            'developer_message': developer_message,
            'user_message': user_message
        }
        return bad_request_dict

    @mock.patch.object(BasketCreateView, '_checkout', mock.Mock(side_effect=ValueError('Test message')))
    def test_checkout_exception(self):
        """ If an exception is raised when initiating the checkout process, a PaymentProcessorResponse should be
        recorded, and the view should return HTTP status 500. """

        self.user.baskets.all().delete()
        response = self.create_basket(skus=[self.PAID_SKU], checkout=True)

        # Verify no new basket was persisted to the database
        self.assertEqual(self.user.baskets.count(), 0)

        # Validate the response status and content
        self.assertEqual(response.status_code, 500)
        actual = json.loads(response.content)
        expected = {
            'developer_message': 'Test message'
        }
        self.assertDictEqual(actual, expected)


class OrderByBasketRetrieveViewTests(OrderDetailViewTestMixin, TestCase):
    """Test cases for getting orders using the basket id. """

    @property
    def url(self):
        return reverse('api:v2:baskets:retrieve_order', kwargs={'basket_id': self.order.basket.id})

    def test_deleted_basket(self):
        """ Verify the endpoint can retrieve an order even if the basket has been deleted. """
        url = self.url
        self.order.basket.delete()

        response = self.client.get(url, HTTP_AUTHORIZATION=self.token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.serialize_order(self.order))


class BasketDestroyViewTests(TestCase):
    def setUp(self):
        super(BasketDestroyViewTests, self).setUp()
        self.basket = BasketFactory()
        self.url = reverse('api:v2:baskets:destroy', kwargs={'basket_id': self.basket.id})

    def test_authorization(self):
        """ Verify regular users cannot delete baskets. """
        user = self.create_user()
        self.client.login(username=user.username, password=self.password)
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Basket.objects.filter(id=self.basket.id).exists())

    def test_deletion(self):
        """ Verify superusers can delete baskets. """
        superuser = self.create_user(is_superuser=True)
        self.client.login(username=superuser.username, password=self.password)
        response = self.client.delete(self.url)

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Basket.objects.filter(id=self.basket.id).exists())
