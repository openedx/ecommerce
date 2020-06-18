

import datetime

import ddt
import pytz
from django.test import RequestFactory
from oscar.apps.partner import availability

from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.extensions.partner.strategy import DefaultStrategy, Selector
from ecommerce.tests.testcases import TestCase


@ddt.ddt
class DefaultStrategyTests(DiscoveryTestMixin, TestCase):
    def setUp(self):
        super(DefaultStrategyTests, self).setUp()
        self.strategy = DefaultStrategy()
        course = CourseFactory(id='a/b/c', name='Demo Course', partner=self.partner)
        self.honor_seat = course.create_or_update_seat('honor', False, 0)

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

    @ddt.unpack
    @ddt.data(
        (True, availability.Available),
        (False, availability.Unavailable),
    )
    def test_expired_seats_availability_for_users(self, is_staff, available):
        """ A product is unavailable for students if the current date
        is beyond the product's expiration date. But for Admin products
        are always available.
        """
        self.assert_expired_product_availability(is_staff, available)

    def assert_expired_product_availability(self, is_staff, available):
        request = RequestFactory()
        request.user = self.create_user(is_staff=is_staff)
        strategy = DefaultStrategy(request)
        product = self.honor_seat
        product.expires = pytz.utc.localize(datetime.datetime.min)
        stock_record = product.stockrecords.first()
        actual = strategy.availability_policy(product, stock_record)
        self.assertIsInstance(actual, available)


class SelectorTests(TestCase):
    def test_strategy(self):
        """ Verify our own DefaultStrategy is returned. """
        actual = Selector().strategy()
        self.assertIsInstance(actual, DefaultStrategy)
