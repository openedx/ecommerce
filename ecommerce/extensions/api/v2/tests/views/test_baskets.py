# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

from decimal import Decimal

import ddt
from django.contrib.auth import get_user_model
from django.test import override_settings
from oscar.core.loading import get_model
from oscar.test import factories

from ecommerce.extensions.api import exceptions as api_exceptions
from ecommerce.extensions.basket.constants import EMAIL_OPT_IN_ATTRIBUTE
from ecommerce.tests.mixins import BasketCreationMixin, ThrottlingMixin
from ecommerce.tests.testcases import TestCase, TransactionTestCase

Basket = get_model('basket', 'Basket')
BasketAttributeType = get_model('basket', 'BasketAttributeType')
Benefit = get_model('offer', 'Benefit')
Category = get_model('catalogue', 'Category')
ConditionalOffer = get_model('offer', 'ConditionalOffer')
Condition = get_model('offer', 'Condition')
Order = get_model('order', 'Order')
ShippingEventType = get_model('order', 'ShippingEventType')
Refund = get_model('refund', 'Refund')
User = get_user_model()
Voucher = get_model('voucher', 'Voucher')

LOGGER_NAME = 'ecommerce.extensions.api.v2.views.baskets'


@ddt.ddt
@override_settings(
    FULFILLMENT_MODULES=['ecommerce.extensions.fulfillment.tests.modules.FakeFulfillmentModule']
)
# Why TransactionTestCase? See http://stackoverflow.com/a/23326971.
class BasketCreateViewTests(BasketCreationMixin, ThrottlingMixin, TransactionTestCase):
    FREE_SKU = 'FREE_PRODUCT'
    PAID_SKU = 'PAID_PRODUCT'
    ALTERNATE_FREE_SKU = 'ALTERNATE_FREE_PRODUCT'
    ALTERNATE_PAID_SKU = 'ALTERNATE_PAID_PRODUCT'
    BAD_SKU = 'not-a-sku'
    UNAVAILABLE = False
    UNAVAILABLE_MESSAGE = 'Unavailable'
    FAKE_PROCESSOR_NAME = 'awesome-processor'

    def setUp(self):
        super(BasketCreateViewTests, self).setUp()

        print('### In BasketCreateViewTests.setUp, after super')

        categories = Category.objects.all()
        print('### length before paid_product: ' + str(len(categories)))
        cat = Category.objects.order_by('-id').first()
        if cat is not None:
            print('### last cat before paid_product: id=' + str(cat.id) + ', path=' + str(cat.path) + ', depth=' + str(cat.depth) + ', numchild=' + str(cat.numchild) + ', name=' + str(cat.name) + ', desc=' + str(cat.description) + ', slug=' + str(cat.slug))
        self.paid_product = factories.ProductFactory(
            structure='child',
            parent=self.base_product,
            title='LP 560-4',
            stockrecords__partner_sku=self.PAID_SKU,
            stockrecords__price_excl_tax=Decimal('180000.00'),
            stockrecords__partner__short_code='oscr',
        )

        categories = Category.objects.all()
        print('### length before papier: ' + str(len(categories)))
        cat = Category.objects.order_by('-id').first()
        if cat is not None:
            print('### last cat before papier: id=' + str(cat.id) + ', path=' + str(cat.path) + ', depth=' + str(cat.depth) + ', numchild=' + str(cat.numchild) + ', name=' + str(cat.name) + ', desc=' + str(cat.description) + ', slug=' + str(cat.slug))
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
            title='LP 570-4 Superleggera',
            stockrecords__partner_sku=self.ALTERNATE_PAID_SKU,
            stockrecords__price_excl_tax=Decimal('240000.00'),
            stockrecords__partner__short_code='dummy',
        )
        # Ensure that the basket attribute type exists for these tests
        basket_attribute_type, _ = BasketAttributeType.objects.get_or_create(name=EMAIL_OPT_IN_ATTRIBUTE)
        basket_attribute_type.save()

    @ddt.data(
        ([FREE_SKU], False, None, False),
    )
    @ddt.unpack
    def test_basket_creation_and_checkout(self, skus, checkout, payment_processor_name, requires_payment):
        """Test that a variety of product combinations can be added to the basket and purchased."""
        print('### In test_basket_creation_and_checkout')
        self.assertTrue(False)
        self.assert_successful_basket_creation(skus, checkout, payment_processor_name, requires_payment)

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
        self.assertTrue(False)

    def _bad_request_dict(self, developer_message, user_message):
        bad_request_dict = {
            'developer_message': developer_message,
            'user_message': user_message
        }
        return bad_request_dict


