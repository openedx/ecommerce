from django.test import RequestFactory
from oscar.test.factories import OrderDiscountFactory, SourceFactory

from ecommerce.extensions.iap.api.v1.serializers import MobileOrderSerializer
from ecommerce.extensions.test import factories
from ecommerce.tests.testcases import TestCase


class MobileOrderSerializerTests(TestCase):
    """ Test for order serializers. """
    LOGGER_NAME = 'ecommerce.extensions.iap.api.v1.serializers'

    def setUp(self):
        super(MobileOrderSerializerTests, self).setUp()
        self.user = self.create_user()

    def test_get_payment_processor(self):
        order = factories.create_order(site=self.site, user=self.user)
        source = SourceFactory(order=order)
        order.sources.add(source)
        payment_processor_name = source.source_type.name
        serializer = MobileOrderSerializer(order,
                                           context={'request': RequestFactory(SERVER_NAME=self.site.domain).get('/')})
        self.assertEqual(serializer.get_payment_processor(order), payment_processor_name)

    def test_get_payment_processor_error(self):
        order = factories.create_order(site=self.site, user=self.user)
        order.sources.all().delete()
        serializer = MobileOrderSerializer(order,
                                           context={'request': RequestFactory(SERVER_NAME=self.site.domain).get('/')})
        payment_processor = serializer.get_payment_processor(order)
        self.assertIsNone(payment_processor)

    def test_get_discount(self):
        order = factories.create_order(site=self.site, user=self.user)
        expected_discount = OrderDiscountFactory(order=order)
        expected_discount_amount = 100.00
        expected_discount_amount_str = '100.00'
        expected_discount.amount = expected_discount_amount
        expected_discount.save()
        serializer = MobileOrderSerializer(order,
                                           context={'request': RequestFactory(SERVER_NAME=self.site.domain).get('/')})
        actual_discount = serializer.get_discount(order)
        self.assertEqual(actual_discount, expected_discount_amount_str)

    def test_get_discount_error(self):
        order = factories.create_order(site=self.site, user=self.user)
        order.discounts.all().delete()
        serializer = MobileOrderSerializer(order,
                                           context={'request': RequestFactory(SERVER_NAME=self.site.domain).get('/')})
        actual_discount = serializer.get_discount(order)
        self.assertEqual(actual_discount, '0')
