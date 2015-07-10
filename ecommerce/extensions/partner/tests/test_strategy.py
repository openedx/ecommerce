import datetime

from django.test import TestCase
from oscar.apps.partner import availability
import pytz

from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.extensions.partner.strategy import DefaultStrategy, Selector


class DefaultStrategyTests(CourseCatalogTestMixin, TestCase):
    def setUp(self):
        super(DefaultStrategyTests, self).setUp()
        self.strategy = DefaultStrategy()
        self.honor_seat = self.create_course_seats('a/b/c', ('honor',))['honor']

    def test_seat_class(self):
        """ Verify the property returns the course seat Product Class. """
        self.assertEqual(self.strategy.seat_class, self.seat_product_class)

    def test_availability_policy_not_expired(self):
        """ If the course seat's expiration date has not passed, the seat should be available for purchase. """
        product = self.honor_seat
        product.expires = None
        stock_record = product.stockrecords.first()
        actual = self.strategy.availability_policy(self.honor_seat, stock_record)
        self.assertIsInstance(actual, availability.Available)

        product.expires = pytz.utc.localize(datetime.datetime.max)
        actual = self.strategy.availability_policy(product, stock_record)
        self.assertIsInstance(actual, availability.Available)

    def test_availability_policy_expired(self):
        """ If the course seat's expiration date has passed, the seat should NOT be available for purchase. """
        product = self.honor_seat
        product.expires = pytz.utc.localize(datetime.datetime.min)
        stock_record = product.stockrecords.first()
        actual = self.strategy.availability_policy(product, stock_record)
        self.assertIsInstance(actual, availability.Unavailable)


class SelectorTests(TestCase):
    def test_strategy(self):
        """ Verify our own DefaultStrategy is returned. """
        actual = Selector().strategy()
        self.assertIsInstance(actual, DefaultStrategy)
