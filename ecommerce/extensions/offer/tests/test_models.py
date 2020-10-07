# -*- coding: utf-8 -*-


from uuid import uuid4

import ddt
import httpretty
from django.core.exceptions import ValidationError
from edx_django_utils.cache import TieredCache
from mock import patch
from oscar.core.loading import get_model
from oscar.test import factories
from requests.exceptions import ConnectionError as ReqConnectionError
from requests.exceptions import Timeout
from slumber.exceptions import SlumberBaseException

from ecommerce.coupons.tests.mixins import CouponMixin, DiscoveryMockMixin
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.extensions.offer.constants import ASSIGN, REMIND, REVOKE
from ecommerce.tests.factories import UserFactory
from ecommerce.tests.testcases import TestCase

Catalog = get_model('catalogue', 'Catalog')
ConditionalOffer = get_model('offer', 'ConditionalOffer')
OfferAssignmentEmailTemplates = get_model('offer', 'OfferAssignmentEmailTemplates')
OfferAssignmentEmailSentRecord = get_model('offer', 'OfferAssignmentEmailSentRecord')
Range = get_model('offer', 'Range')


@ddt.ddt
@httpretty.activate
class RangeTests(CouponMixin, DiscoveryTestMixin, DiscoveryMockMixin, TestCase):
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

    def tearDown(self):
        # Reset HTTPretty state (clean up registered urls and request history)
        httpretty.reset()

    def _assert_num_requests(self, count):
        """
        DRY helper for verifying request counts.
        """
        self.assertEqual(len(httpretty.httpretty.latest_requests), count)

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
        self.range.course_seat_types = 'verified'
        self.range.save()
        self.assertEqual(self.range.catalog_query, large_query)

    def test_course_catalog_query_range_contains_product(self):
        """
        Verify that the method "contains_product" returns True (boolean) if a
        product is in it's range for a course catalog Range.
        """
        catalog_query = 'key:*'
        course, seat = self.create_course_and_seat()
        self.mock_access_token_response()
        self.mock_catalog_query_contains_endpoint(
            query=catalog_query, course_run_ids=[course.id], course_uuids=[], absent_ids=[],
            discovery_api_url=self.site_configuration.discovery_api_url,
        )

        false_response = self.range.contains_product(seat)
        self.assertFalse(false_response)

        course_catalog_id = 1
        self.mock_catalog_contains_endpoint(
            discovery_api_url=self.site_configuration.discovery_api_url, catalog_id=course_catalog_id,
            course_run_ids=[course.id]
        )
        self.range.catalog_query = None
        self.range.course_seat_types = 'verified'
        self.range.course_catalog = course_catalog_id
        self.range.save()

        response = self.range.contains_product(seat)
        self.assertTrue(response)
        # Verify that there only one call for the course discovery API for
        # checking if course exists in course runs against the course catalog.
        self._assert_num_requests(2)

    @ddt.data(ReqConnectionError, SlumberBaseException, Timeout)
    def test_course_catalog_query_range_contains_product_for_failure(self, error):
        """
        Verify that the method "contains_product" raises exception if the
        method "catalog_contains_product" is unable to get the catalog from
        Discovery Service for a course catalog Range.
        """
        __, seat = self.create_course_and_seat()
        course_catalog_id = 1
        self.range.catalog_query = None
        self.range.course_seat_types = 'verified'
        self.range.course_catalog = course_catalog_id
        self.range.save()

        self.mock_access_token_response()
        self.mock_discovery_api_failure(error, self.site_configuration.discovery_api_url, course_catalog_id)
        with self.assertRaises(Exception) as err:
            self.range.contains_product(seat)

        expected_exception_message = 'Unable to connect to Discovery Service for catalog contains endpoint.'
        self.assertEqual(str(err.exception), expected_exception_message)
        # Verify that there only one call for the course discovery API for
        # checking if course exists in course runs against the course catalog.
        self._assert_num_requests(2)

    @ddt.data(
        'verified',
        'verified,professional',
    )
    def test_course_catalog_range_contains_product(self, range_course_seat_types):
        """
        Verify that the method "contains_product" returns True (boolean) if a
        product seat is in it's range for a course catalog.
        """
        # Create a course with verified seat type
        course, seat = self.create_course_and_seat()

        course_catalog = 1
        self.range.catalog_query = None
        self.range.course_seat_types = range_course_seat_types
        self.range.course_catalog = course_catalog
        self.range.save()

        self.mock_access_token_response()
        self.mock_catalog_contains_endpoint(
            discovery_api_url=self.site_configuration.discovery_api_url, catalog_id=course_catalog,
            course_run_ids=[course.id]
        )
        is_product_in_range = self.range.contains_product(seat)
        self.assertTrue(is_product_in_range)
        # Verify that there only one call for the course discovery API for
        # checking if course exists in course runs against the course catalog.
        self._assert_num_requests(2)

    @ddt.data(
        ('verified', 'professional'),
        ('professional', 'verified'),
    )
    @ddt.unpack
    def test_course_catalog_range_contains_product_for_invalid_seat(self, range_course_seat_type, invalid_seat_type):
        """
        Verify that the method "contains_product" returns False (boolean) if a
        product seat is not in it's range for a course catalog.
        """
        course, __ = self.create_course_and_seat(seat_type=range_course_seat_type)
        __, invalid_course_seat = self.create_course_and_seat(seat_type=invalid_seat_type)

        course_catalog = 1
        self.range.catalog_query = None
        self.range.course_seat_types = range_course_seat_type
        self.range.course_catalog = course_catalog
        self.range.save()

        self.mock_access_token_response()
        self.mock_catalog_contains_endpoint(
            discovery_api_url=self.site_configuration.discovery_api_url, catalog_id=course_catalog,
            course_run_ids=[course.id]
        )
        is_product_in_range = self.range.contains_product(invalid_course_seat)
        self.assertFalse(is_product_in_range)
        # Verify that there was no call for the course discovery API as Range
        # doesn't have the provide course seat types.
        self._assert_num_requests(0)

    def test_query_range_all_products(self):
        """
        all_products() should return seats from the query.
        """
        course, seat = self.create_course_and_seat()
        self.assertEqual(len(self.range.all_products()), 1)
        self.assertFalse(seat in self.range.all_products())

        self.mock_access_token_response()
        self.mock_course_runs_endpoint(
            self.site_configuration.discovery_api_url, query='key:*', course_run=course
        )
        self.range.catalog_query = 'key:*'
        self.range.course_seat_types = 'verified'
        self.assertEqual(len(self.range.all_products()), 0)

    @ddt.data(
        {'catalog_query': '*:*'},
        {'catalog_query': '', 'course_seat_types': ['verified']},
        {'course_seat_types': ['verified']},
        {'course_catalog': '', 'course_seat_types': 'verified'},
        {'course_catalog': '20'},
        {'course_catalog': '20', 'catalog_query': '*:*'},
        {'course_catalog': '20', 'catalog_query': '*:*', 'course_seat_types': 'verified'},
    )
    def test_creating_range_with_wrong_data(self, data):
        """
        Verify creating range raises ValidationError:
            - without course_catalog or catalog_query or catalog_seat_types.
            - with both given course_catalog and catalog_query.
        """
        with self.assertRaises(ValidationError):
            Range.objects.create(**data)

    @ddt.data(
        {'catalog_query': '*:*'},
        {'catalog_query': '*:*', 'course_seat_types': ['verified']},
        {'course_seat_types': ['verified']}
    )
    def test_creating_range_with_catalog_and_dynamic_fields(self, data):
        """Verify creating range with catalog and dynamic fields set will raise exception."""
        data.update({'catalog': self.catalog})
        with self.assertRaises(ValidationError):
            Range.objects.create(**data)

    def test_creating_dynamic_range(self):
        """Verify creating range with catalog_query or catalog_seat_types creates range with those values."""
        data = {
            'catalog_query': 'id:testquery',
            'course_seat_types': 'verified,professional'
        }
        new_range = Range.objects.create(**data)
        self.assertEqual(new_range.catalog_query, data['catalog_query'])
        self.assertEqual(new_range.course_seat_types, data['course_seat_types'])
        self.assertEqual(new_range.catalog, None)

    def test_creating_dynamic_range_with_course_catalog(self):
        """
        Verify creating range with course_catalog and catalog_seat_types creates
        range with those values.
        """
        data = {
            'course_catalog': '10',
            'course_seat_types': 'verified,professional'
        }
        new_range = Range.objects.create(**data)
        self.assertEqual(new_range.course_catalog, data['course_catalog'])
        self.assertEqual(new_range.course_seat_types, data['course_seat_types'])
        self.assertEqual(new_range.catalog, None)

    @ddt.data(5, 'credit,verified', 'verified,not_allowed_value')
    def test_creating_range_with_wrong_course_seat_types(self, course_seat_types):
        """ Verify creating range with incorrect course seat types will raise exception. """
        data = {
            'catalog_query': '*:*',
            'course_seat_types': course_seat_types
        }
        with self.assertRaises(ValidationError):
            Range.objects.create(**data)

    @ddt.data('credit', 'professional', 'verified', 'professional,verified')
    def test_creating_range_with_course_seat_types(self, course_seat_types):
        """ Verify creating range with allowed course seat types values creates range. """
        data = {
            'catalog_query': '*:*',
            'course_seat_types': course_seat_types
        }
        _range = Range.objects.create(**data)
        self.assertEqual(_range.course_seat_types, course_seat_types)

    def test_catalog_contains_product(self):
        """
        Verify that catalog_contains_product is cached

        We expect 2 calls to set_all_tiers due to:
            - the site_configuration api setup
            - the result being cached
        """
        self.mock_access_token_response()

        course, __ = self.create_course_and_seat()
        course_catalog_id = 1
        self.range.catalog_query = None
        self.range.course_seat_types = 'verified'
        self.range.course_catalog = course_catalog_id
        self.range.save()
        self.product.course = course
        self.product.save()

        self.mock_catalog_contains_endpoint(
            discovery_api_url=self.site_configuration.discovery_api_url, catalog_id=course_catalog_id,
            course_run_ids=[course.id]
        )

        with patch.object(TieredCache, 'set_all_tiers', wraps=TieredCache.set_all_tiers) as mocked_set_all_tiers:
            mocked_set_all_tiers.assert_not_called()

            _ = self.range.catalog_contains_product(self.product)
            self.assertEqual(mocked_set_all_tiers.call_count, 2)

            _ = self.range.catalog_contains_product(self.product)
            self.assertEqual(mocked_set_all_tiers.call_count, 2)


@ddt.ddt
@httpretty.activate
class ConditionalOfferTests(DiscoveryTestMixin, DiscoveryMockMixin, TestCase):
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
        basket = factories.BasketFactory(owner=user, site=self.site)
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

    def test_condition_not_satisfied_for_enterprise(self):
        """Verify a condition is not satisfied."""
        valid_user_email = 'valid@{domain}'.format(domain=self.valid_sub_domain)
        basket = factories.BasketFactory(site=self.site, owner=UserFactory(email=valid_user_email))

        _range = factories.RangeFactory(
            products=[self.product, ],
            course_seat_types='verified',
            enterprise_customer=str(uuid4()),
            catalog_query='*:*'
        )
        benefit = factories.BenefitFactory(range=_range)
        offer = factories.ConditionalOfferFactory(benefit=benefit)

        basket.add_product(self.product)
        self.assertFalse(offer.is_condition_satisfied(basket))

    def test_is_range_condition_satisfied(self):
        """
        Verify that a basket satisfies a condition only when all of its products are in its range's catalog queryset.
        """
        valid_user_email = 'valid@{domain}'.format(domain=self.valid_sub_domain)
        basket = factories.BasketFactory(site=self.site, owner=UserFactory(email=valid_user_email))
        product = self.create_entitlement_product()
        another_product = self.create_entitlement_product()

        _range = factories.RangeFactory()
        _range.course_seat_types = ','.join(Range.ALLOWED_SEAT_TYPES)
        _range.catalog_query = 'uuid:{course_uuid}'.format(course_uuid=product.attr.UUID)
        benefit = factories.BenefitFactory(range=_range)
        offer = factories.ConditionalOfferFactory(benefit=benefit)
        self.mock_access_token_response()
        self.mock_catalog_query_contains_endpoint(
            course_run_ids=[], course_uuids=[product.attr.UUID], absent_ids=[another_product.attr.UUID],
            query=benefit.range.catalog_query, discovery_api_url=self.site_configuration.discovery_api_url
        )

        basket.add_product(product)
        self.assertTrue(offer.is_condition_satisfied(basket))

        basket.add_product(another_product)
        self.assertFalse(offer.is_condition_satisfied(basket))

        # Verify that API return values are cached
        httpretty.disable()
        self.assertFalse(offer.is_condition_satisfied(basket))

    def test_is_single_use_range_condition_satisfied(self):
        """
        Verify that the condition for a single use coupon is only satisfied by single-product baskets.
        """
        valid_user_email = 'valid@{domain}'.format(domain=self.valid_sub_domain)
        basket = factories.BasketFactory(site=self.site, owner=UserFactory(email=valid_user_email))
        product1 = self.create_entitlement_product()
        product2 = self.create_entitlement_product()

        _range = factories.RangeFactory()
        _range.course_seat_types = ','.join(Range.ALLOWED_SEAT_TYPES)
        _range.catalog_query = 'uuid:*'
        benefit = factories.BenefitFactory(range=_range)
        offer = factories.ConditionalOfferFactory(benefit=benefit)
        offer.set_voucher(
            factories.VoucherFactory(usage='Single-use')
        )
        self.mock_access_token_response()
        self.mock_catalog_query_contains_endpoint(
            course_run_ids=[], course_uuids=[product1.attr.UUID, product2.attr.UUID], absent_ids=[],
            query=benefit.range.catalog_query, discovery_api_url=self.site_configuration.discovery_api_url
        )

        # Verify that each product individually satisfies the condition
        basket.add_product(product1)
        self.assertTrue(offer.is_condition_satisfied(basket))

        basket.flush()
        basket.add_product(product2)
        self.assertTrue(offer.is_condition_satisfied(basket))

        # Verify that the offer cannot be applied to a multi-product basket
        basket.add_product(product1)
        self.assertFalse(offer.is_condition_satisfied(basket))

    def test_is_email_valid(self):
        """Verify method returns True for valid emails."""
        invalid_email = 'invalid@email.fake'
        self.assertFalse(self.offer.is_email_valid(invalid_email))

        valid_email = 'valid@{domain}'.format(domain=self.valid_sub_domain)
        self.assertTrue(self.offer.is_email_valid(valid_email))

        valid_uppercase_email = 'valid@{domain}'.format(domain=self.valid_sub_domain.upper())
        self.assertTrue(self.offer.is_email_valid(valid_uppercase_email))

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

    @ddt.data(
        '', 'domain.com', 'multi.it,domain.hr', 'sub.domain.net', '例如.com', 'val-id.例如', 'valid1.co例如',
        'valid-domain.com', 'çççç.рф', 'çç-ççç32.中国', 'ççç.ççç.இலங்கை'
    )
    def test_creating_offer_with_valid_email_domains(self, email_domains):
        """Verify creating ConditionalOffer with valid email domains."""
        offer = factories.ConditionalOfferFactory(email_domains=email_domains)
        self.assertEqual(offer.email_domains, email_domains)

    @ddt.data(
        'noDot', 'spaceAfter.comma, domain.hr', 'nothingAfterDot.', '.nothingBeforeDot', 'space not.allowed',
        3, '-invalid.com', 'invalid', 'invalid-.com', 'invalid.c', 'valid.com,', 'invalid.photography1',
        'valid.com,invalid', 'valid.com,invalid-.com', 'valid.com,-invalid.com', 'in--valid.com',
        'in..valid.com', 'valid.com,invalid.c', 'invalid,valid.com', 'çççç.çç-çç', 'ççç.xn--ççççç', 'çççç.çç--çç.ççç'
    )
    def test_creating_offer_with_invalid_email_domains(self, email_domains):
        """Verify creating ConditionalOffer with invalid email domains raises validation error."""
        with self.assertRaises(ValidationError):
            factories.ConditionalOfferFactory(email_domains=email_domains)

    def test_creating_offer_with_valid_max_global_applications(self):
        """Verify creating ConditionalOffer with valid max global applications value."""
        offer = factories.ConditionalOfferFactory(max_global_applications=5)
        self.assertEqual(offer.max_global_applications, 5)

    @ddt.data(-2, 0, 'string', '')
    def test_creating_offer_with_invalid_max_global_applications(self, max_uses):
        """Verify creating ConditionalOffer with invalid max global applications value raises validation error."""
        with self.assertRaises(ValidationError):
            factories.ConditionalOfferFactory(max_global_applications=max_uses)

    def test_creating_offer_with_partner(self):
        """Verify creating ConditionalOffer with partner specified"""
        offer = factories.ConditionalOfferFactory(partner=self.partner)
        self.assertEqual(offer.partner, self.partner)

    def test_creating_offer_with_null_partner(self):
        """Verify creating ConditionalOffer with no partner specified"""
        offer = factories.ConditionalOfferFactory()
        self.assertEqual(offer.partner, None)


class BenefitTests(DiscoveryTestMixin, DiscoveryMockMixin, TestCase):
    def setUp(self):
        super(BenefitTests, self).setUp()

        _range = factories.RangeFactory(
            course_seat_types=','.join(Range.ALLOWED_SEAT_TYPES[1:]),
            catalog_query='uuid:*'
        )
        self.benefit = factories.BenefitFactory(range=_range)
        self.offer = factories.ConditionalOfferFactory(benefit=self.benefit)
        self.user = UserFactory()

    def test_range(self):
        with self.assertRaises(ValidationError):
            factories.BenefitFactory(range=None)

    def test_value(self):
        with self.assertRaises(ValidationError):
            factories.BenefitFactory(value=110)

        with self.assertRaises(ValidationError):
            factories.BenefitFactory(value=-10)

    @httpretty.activate
    def test_get_applicable_lines(self):
        """ Assert that basket lines matching the range's discovery query are selected. """
        basket = factories.BasketFactory(site=self.site, owner=self.user)
        entitlement_product = self.create_entitlement_product()
        course, seat = self.create_course_and_seat()
        no_certificate_product = factories.ProductFactory(stockrecords__price_currency='USD')

        basket.add_product(entitlement_product)
        basket.add_product(seat)
        applicable_lines = [(line.product.stockrecords.first().price_excl_tax, line) for line in basket.all_lines()]
        basket.add_product(no_certificate_product)

        self.mock_access_token_response()

        # Verify that the method raises an exception when it fails to reach the Discovery Service
        with self.assertRaises(Exception):
            self.benefit.get_applicable_lines(self.offer, basket)

        self.mock_catalog_query_contains_endpoint(
            course_run_ids=[], course_uuids=[entitlement_product.attr.UUID, course.id], absent_ids=[],
            query=self.benefit.range.catalog_query, discovery_api_url=self.site_configuration.discovery_api_url
        )

        self.assertEqual(self.benefit.get_applicable_lines(self.offer, basket), applicable_lines)

        # Verify that the API return value is cached
        httpretty.disable()
        self.assertEqual(self.benefit.get_applicable_lines(self.offer, basket), applicable_lines)


@ddt.ddt
class TestOfferAssignmentEmailSentRecord(TestCase):
    """Tests for the TestOfferAssignmentEmailSentRecord model."""

    def _create_template(self, enterprise_customer, email_type):
        """Helper method to create OfferAssignmentEmailTemplates instance with the given email type."""
        return OfferAssignmentEmailTemplates.objects.create(
            enterprise_customer=enterprise_customer,
            email_type=email_type,
            email_greeting='test greeting',
            email_closing='test closing',
            email_subject='template subject',
            active=True,
            name='test template'
        )

    def _create_email_sent_record(self, enterprise_customer, email_type, template):
        """Helper method to create instance of OfferAssignmentEmailSentRecord."""
        return OfferAssignmentEmailSentRecord.create_email_record(enterprise_customer, email_type, template)

    @ddt.data(
        (str(uuid4()), ASSIGN),
        (str(uuid4()), REMIND),
        (str(uuid4()), REVOKE),
    )
    @ddt.unpack
    def test_string_representation(self, enterprise_customer, email_type):
        """
        Test the string representation of the TestOfferAssignmentEmailSentRecord model.
        """
        template = self._create_template(enterprise_customer, email_type)
        email_record = self._create_email_sent_record(enterprise_customer, email_type, template)
        expected_str = '{ec}-{email_type}'.format(ec=enterprise_customer, email_type=email_type)
        assert expected_str == email_record.__str__()

    @ddt.data(
        (str(uuid4()), ASSIGN),
        (str(uuid4()), REMIND),
        (str(uuid4()), REVOKE),
    )
    @ddt.unpack
    def test_create_email_record(self, enterprise_customer, email_type):
        """
        OfferAssignmentEmailSentRecord.create_email_record should create email record with given enterprise_customer,
        email_type, and template.
        """
        # Verify that no record has been created yet
        assert OfferAssignmentEmailSentRecord.objects.count() == 0
        template = self._create_template(enterprise_customer, email_type)
        email_record = OfferAssignmentEmailSentRecord.create_email_record(enterprise_customer, email_type, template)
        # Verify that the class method created a record
        assert OfferAssignmentEmailSentRecord.objects.count() == 1

        # Verify that record was created with the provided values
        assert email_record.enterprise_customer == enterprise_customer
        assert email_record.email_type == email_type
        assert email_record.template_id == template.id
