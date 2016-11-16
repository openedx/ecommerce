import hashlib

import httpretty
import mock
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import RequestFactory
from oscar.core.loading import get_model
from oscar.test import factories

from ecommerce.core.tests.decorators import mock_course_catalog_api_client
from ecommerce.coupons.tests.mixins import CourseCatalogMockMixin, CouponMixin
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.extensions.offer.models import validate_credit_seat_type
from ecommerce.tests.testcases import TestCase

Catalog = get_model('catalogue', 'Catalog')
ConditionalOffer = get_model('offer', 'ConditionalOffer')


class RangeTests(CouponMixin, CourseCatalogTestMixin, CourseCatalogMockMixin, TestCase):
    def setUp(self):
        super(RangeTests, self).setUp()

        self.range = factories.RangeFactory()
        self.range_with_catalog = factories.RangeFactory()

        self.catalog = Catalog.objects.create(partner=self.partner)
        self.product = factories.create_product()

        self.range.add_product(self.product)
        self.range_with_catalog.catalog = self.catalog
        self.stock_record = factories.create_stockrecord(self.product, num_in_stock=2)
        self.catalog.stock_records.add(self.stock_record)

    def test_range_contains_product(self):
        """
        contains_product(product) should return Boolean value
        """
        self.assertTrue(self.range.contains_product(self.product))
        self.assertTrue(self.range_with_catalog.contains_product(self.product))

        not_in_range_product = factories.create_product()
        self.assertFalse(self.range.contains_product(not_in_range_product))
        self.assertFalse(self.range.contains_product(not_in_range_product))

    def test_range_number_of_products(self):
        """
        num_products() should return number of num_of_products
        """
        self.assertEqual(self.range.num_products(), 1)
        self.assertEqual(self.range_with_catalog.num_products(), 1)

    def test_range_all_products(self):
        """
        all_products() should return a list of products in range
        """
        self.assertIn(self.product, self.range.all_products())
        self.assertEqual(len(self.range.all_products()), 1)

        self.assertIn(self.product, self.range_with_catalog.all_products())
        self.assertEqual(len(self.range_with_catalog.all_products()), 1)

    def test_large_query(self):
        """Verify the range can store large queries."""
        large_query = """
            Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod
            tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam,
            quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo
            consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse
            cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat
            non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.
        """
        self.range.catalog_query = large_query
        self.range.save()
        self.assertEqual(self.range.catalog_query, large_query)

    @mock.patch('ecommerce.core.url_utils.get_current_request', mock.Mock(return_value=None))
    def test_run_catalog_query_no_request(self):
        """
        run_course_query() should return status 400 response when no request is present.
        """
        with self.assertRaises(Exception):
            self.range.run_catalog_query(self.product)

    @httpretty.activate
    @mock_course_catalog_api_client
    def test_run_catalog_query(self):
        """
        run_course_query() should return True for included course run ID's.
        """
        course, seat = self.create_course_and_seat()
        self.mock_dynamic_catalog_contains_api(query='key:*', course_run_ids=[course.id])
        request = RequestFactory()
        request.site = self.site
        self.range.catalog_query = 'key:*'

        cache_key = 'catalog_query_contains [{}] [{}]'.format('key:*', seat.course_id)
        cache_key = hashlib.md5(cache_key).hexdigest()
        cached_response = cache.get(cache_key)
        self.assertIsNone(cached_response)

        with mock.patch('ecommerce.core.url_utils.get_current_request', mock.Mock(return_value=request)):
            response = self.range.run_catalog_query(seat)
            self.assertTrue(response['course_runs'][course.id])
            cached_response = cache.get(cache_key)
            self.assertEqual(response, cached_response)

    @httpretty.activate
    @mock_course_catalog_api_client
    def test_query_range_contains_product(self):
        """
        contains_product() should return the correct boolean if a product is in it's range.
        """
        course, seat = self.create_course_and_seat()
        self.mock_dynamic_catalog_contains_api(query='key:*', course_run_ids=[course.id])

        false_response = self.range.contains_product(seat)
        self.assertFalse(false_response)

        self.range.catalog_query = 'key:*'
        self.range.course_seat_types = 'verified'
        response = self.range.contains_product(seat)
        self.assertTrue(response)

    @httpretty.activate
    @mock_course_catalog_api_client
    def test_query_range_all_products(self):
        """
        all_products() should return seats from the query.
        """
        course, seat = self.create_course_and_seat()
        self.assertEqual(len(self.range.all_products()), 1)
        self.assertFalse(seat in self.range.all_products())

        self.mock_dynamic_catalog_course_runs_api(query='key:*', course_run=course)
        self.range.catalog_query = 'key:*'
        self.range.course_seat_types = 'verified'
        self.assertEqual(len(self.range.all_products()), 0)

    def test_credit_seat_type_validator(self):
        """
        Verify the validator raises error for combination of credit and another seat type.
        """
        self.assertIsNone(validate_credit_seat_type('verified,professional'))
        self.assertIsNone(validate_credit_seat_type('credit'))

        with self.assertRaises(ValidationError):
            validate_credit_seat_type('credit,verified')


class ConditionalOfferTests(TestCase):
    """Tests for custom ConditionalOffer model."""
    def setUp(self):
        super(ConditionalOfferTests, self).setUp()

        self.valid_domain = 'example.com'
        self.valid_sub_domain = 'sub.example2.com'
        self.email_domains = '{domain1},{domain2}'.format(
            domain1=self.valid_domain,
            domain2=self.valid_sub_domain
        )
        self.product = factories.ProductFactory()
        _range = factories.RangeFactory(products=[self.product, ])

        self.offer = ConditionalOffer.objects.create(
            condition=factories.ConditionFactory(value=1, range=_range),
            benefit=factories.BenefitFactory(),
            email_domains=self.email_domains
        )

    def create_basket(self, email):
        """Helper method for creating a basket with specific owner."""
        user = self.create_user(email=email)
        basket = factories.BasketFactory(owner=user)
        basket.add_product(self.product, 1)
        return basket

    def test_condition_satisfied(self):
        """Verify a condition is satisfied."""
        self.assertEqual(self.offer.email_domains, self.email_domains)
        email = 'test@{domain}'.format(domain=self.valid_domain)
        basket = self.create_basket(email=email)
        self.assertTrue(self.offer.is_condition_satisfied(basket))

    def test_condition_not_satisfied(self):
        """Verify a condition is not satisfied."""
        self.assertEqual(self.offer.email_domains, self.email_domains)
        basket = self.create_basket(email='test@invalid.domain')
        self.assertFalse(self.offer.is_condition_satisfied(basket))

    def test_is_email_valid(self):
        """Verify method returns True for valid emails."""
        invalid_email = 'invalid@email.fake'
        self.assertFalse(self.offer.is_email_valid(invalid_email))

        valid_email = 'valid@{domain}'.format(domain=self.valid_sub_domain)
        self.assertTrue(self.offer.is_email_valid(valid_email))

        no_email_offer = factories.ConditionalOffer()
        self.assertTrue(no_email_offer.is_email_valid(invalid_email))

    def test_is_email_with_sub_domain_valid(self):
        """Verify method returns True for valid email domains with sub domain."""
        invalid_email = 'test@test{domain}'.format(domain=self.valid_sub_domain)  # test@testsub.example2.com
        self.assertFalse(self.offer.is_email_valid(invalid_email))

        valid_email = 'test@{domain}'.format(domain=self.valid_sub_domain)
        self.assertTrue(self.offer.is_email_valid(valid_email))

        valid_email_2 = 'test@sub2.{domain}'.format(domain=self.valid_domain)
        self.assertTrue(self.offer.is_email_valid(valid_email_2))
