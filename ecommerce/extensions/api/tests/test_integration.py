# -*- coding: utf-8 -*-
"""Integration tests of the orders endpoint and fulfillment."""
import logging
from decimal import Decimal as D

import jwt
from django.conf import settings
from django.test import TestCase
from django.test.utils import override_settings
from django.core.urlresolvers import reverse
from oscar.test import factories
from oscar.core.loading import get_model
from rest_framework import status

from ecommerce.extensions.api.serializers import OrderSerializer


Order = get_model('order', 'Order')
ShippingEventType = get_model('order', 'ShippingEventType')


class OrdersIntegrationTests(TestCase):
    USER_DATA = {
        'username': 'sgoodman',
        'email': 'saul@bettercallsaul.com',
    }
    FREE_TRIAL_SKU = u'ṖÜḄḶЇĊ⸚ḊЁḞЁṄḊЁṚ'
    JWT_SECRET_KEY = getattr(settings, 'JWT_AUTH')['JWT_SECRET_KEY']

    def setUp(self):
        # Override all loggers, suppressing logging calls of severity CRITICAL and below
        logging.disable(logging.CRITICAL)

        self.product_class = factories.ProductClassFactory(
            name=u'𝕿𝖗𝖎𝖆𝖑',
            requires_shipping=False,
            track_stock=False
        )
        self.courthouse = factories.ProductFactory(
            structure='parent',
            title=u'𝑩𝒆𝒓𝒏𝒂𝒍𝒊𝒍𝒍𝒐 𝑪𝒐𝒖𝒏𝒕𝒚 𝑨𝒏𝒏𝒆𝒙',
            product_class=self.product_class,
            stockrecords=None,
        )

        self.free_trial = factories.ProductFactory(
            structure='child',
            parent=self.courthouse,
            title=u'𝕋𝕣𝕚𝕒𝕝 𝕨𝕚𝕥𝕙 ℙ𝕦𝕓𝕝𝕚𝕔 𝔻𝕖𝕗𝕖𝕟𝕕𝕖𝕣',
            product_class=self.product_class,
            stockrecords__partner_sku=self.FREE_TRIAL_SKU,
            stockrecords__price_excl_tax=D('0.00'),
        )

        # Ideally, we'd use Oscar's ShippingEventTypeFactory here, but it's not exposed/public.
        shipped_event = ShippingEventType(code='shipped', name='Shipped')
        shipped_event.save()

        # Remove logger override
        self.addCleanup(logging.disable, logging.NOTSET)

    @override_settings(FULFILLMENT_MODULES=['ecommerce.extensions.fulfillment.tests.test_api.FakeFulfillmentModule'])
    def test_order_free_product(self):
        """Test that a free product can be ordered and fulfilled successfully."""
        self._create_and_verify_order(self.FREE_TRIAL_SKU)

    def _order(self, sku):
        data = {'sku': sku}
        token = jwt.encode(self.USER_DATA, self.JWT_SECRET_KEY)

        response = self.client.post(reverse('orders:create_list'), data, HTTP_AUTHORIZATION='JWT ' + token)

        return response

    def _create_and_verify_order(self, sku):
        response = self._order(sku)

        # Verify that the orders endpoint has successfully created the order
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify that the order data in the response is valid
        response_serializer = OrderSerializer(data=response.data)
        self.assertTrue(response_serializer.is_valid())

        # Verify that the returned order metadata lines up with the order in the system
        expected_serializer = OrderSerializer(Order.objects.get())
        self.assertEqual(response_serializer.data, expected_serializer.data)
