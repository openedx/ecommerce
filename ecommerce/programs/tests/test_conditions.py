

import ddt
import httpretty
import mock
from oscar.core.loading import get_model
from oscar.test.factories import BasketFactory
from requests import Timeout
from slumber.exceptions import HttpNotFoundError, SlumberBaseException

from ecommerce.core.constants import COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME
from ecommerce.courses.models import Course
from ecommerce.extensions.test import factories
from ecommerce.programs.tests.mixins import ProgramTestMixin
from ecommerce.tests.factories import ProductFactory, SiteConfigurationFactory, UserFactory
from ecommerce.tests.testcases import TestCase

Product = get_model('catalogue', 'Product')
ProductClass = get_model('catalogue', 'ProductClass')
LOGGER_NAME = 'ecommerce.programs.conditions'


@ddt.ddt
class ProgramCourseRunSeatsConditionTests(ProgramTestMixin, TestCase):
    def setUp(self):
        super(ProgramCourseRunSeatsConditionTests, self).setUp()
        self.condition = factories.ProgramCourseRunSeatsConditionFactory()
        self.test_product = ProductFactory(stockrecords__price_excl_tax=10, categories=[])
        self.site.siteconfiguration.enable_partial_program = True

    def test_name(self):
        """ The name should contain the program's UUID. """
        condition = factories.ProgramCourseRunSeatsConditionFactory()
        expected = 'Basket contains a seat for every course in program {}'.format(condition.program_uuid)
        self.assertEqual(condition.name, expected)

    @httpretty.activate
    def test_is_satisfied_no_enrollments(self):
        """ The method should return True if the basket contains one course run seat corresponding to each
        course in the program. """
        offer = factories.ProgramOfferFactory(partner=self.partner, condition=self.condition)
        basket = BasketFactory(site=self.site, owner=UserFactory())
        program = self.mock_program_detail_endpoint(
            self.condition.program_uuid, self.site_configuration.discovery_api_url
        )

        # Extract one audit and one verified seat for each course
        audit_seats = []
        verified_seats = []

        for course in program['courses']:
            course_run = Course.objects.get(id=course['course_runs'][0]['key'])
            for seat in course_run.seat_products:
                if seat.attr.id_verification_required:
                    verified_seats.append(seat)
                else:
                    audit_seats.append(seat)

        self.mock_user_data(basket.owner.username)
        # Empty baskets should never be satisfied
        basket.flush()
        self.assertTrue(basket.is_empty)
        self.assertFalse(self.condition.is_satisfied(offer, basket))

        # Adding seats of all the courses with the wrong seat type should NOT satisfy the condition.
        basket.flush()
        for seat in audit_seats:
            basket.add_product(seat)
        self.assertFalse(self.condition.is_satisfied(offer, basket))

        # All courses must be represented in the basket.
        # NOTE: We add all but the first verified seat to ensure complete branch coverage of the method.
        basket.flush()
        for verified_seat in verified_seats[1:len(verified_seats)]:
            basket.add_product(verified_seat)
        self.assertFalse(self.condition.is_satisfied(offer, basket))

        # The condition should be satisfied if one valid course run from each course is in the basket.
        basket.add_product(verified_seats[0])
        self.assertTrue(self.condition.is_satisfied(offer, basket))

        # If the user is enrolled with the wrong seat type for courses missing from their basket that are
        # needed for the program, the condition should NOT be satisfied
        basket.flush()
        for verified_seat in verified_seats[1:len(verified_seats)]:
            basket.add_product(verified_seat)
        self.assertFalse(self.condition.is_satisfied(offer, basket))

    @httpretty.activate
    def test_is_satisfied_with_enrollments(self):
        """ The condition should be satisfied if one valid course run from each course is in either the
        basket or the user's enrolled courses and the site has enabled partial program offers. """
        offer = factories.ProgramOfferFactory(partner=self.partner, condition=self.condition)
        basket = BasketFactory(site=self.site, owner=UserFactory())
        program = self.mock_program_detail_endpoint(
            self.condition.program_uuid, self.site_configuration.discovery_api_url
        )

        # Extract one verified seat for each course
        verified_seats = []
        for course in program['courses']:
            course_run = Course.objects.get(id=course['course_runs'][0]['key'])
            for seat in course_run.seat_products:
                if seat.attr.id_verification_required:
                    verified_seats.append(seat)

        # Add verified enrollments for the first two program courses to the mock user data
        enrollments = [
            {'mode': 'verified', 'course_details': {'course_id': program['courses'][0]['course_runs'][0]['key']}},
            {'mode': 'verified', 'course_details': {'course_id': program['courses'][1]['course_runs'][0]['key']}}
        ]
        self.mock_user_data(basket.owner.username, owned_products=enrollments)

        # If the user has not added all of the remaining courses in the program to their basket,
        # the condition should not be satisfied
        basket.flush()
        for seat in verified_seats[2:len(verified_seats) - 1]:
            basket.add_product(seat)
        self.assertFalse(self.condition.is_satisfied(offer, basket))

        # When all courses in the program that the user is not already enrolled in are in their basket
        # and the site allows partial program completion, the condition should be satisfied
        basket.add_product(verified_seats[-1])
        self.assertTrue(self.condition.is_satisfied(offer, basket))

        # If the site does not allow partial program completion and the user does not have all of the program
        # courses in their basket, the condition should not be satisfied
        basket.site.siteconfiguration.enable_partial_program = False
        self.assertFalse(self.condition.is_satisfied(offer, basket))

        # Verify the user enrollments are cached
        basket.site.siteconfiguration.enable_partial_program = True
        httpretty.disable()
        with mock.patch('ecommerce.programs.conditions.get_program',
                        return_value=program):
            self.assertTrue(self.condition.is_satisfied(offer, basket))

    @ddt.data(HttpNotFoundError, SlumberBaseException, Timeout)
    def test_is_satisfied_with_exception_for_programs(self, value):
        """ The method should return False if there is an exception when trying to get program details. """
        offer = factories.ProgramOfferFactory(partner=self.partner, condition=self.condition)
        basket = BasketFactory(site=self.site, owner=UserFactory())
        basket.add_product(self.test_product)

        with mock.patch('ecommerce.programs.conditions.get_program',
                        side_effect=value):
            self.assertFalse(self.condition.is_satisfied(offer, basket))

    @httpretty.activate
    def test_is_satisfied_with_exception_for_enrollments(self):
        """ The method should return True despite having an error at the enrollment check, given 1 course run seat
        corresponding to each course in the program. """
        offer = factories.ProgramOfferFactory(partner=self.partner, condition=self.condition)
        basket = BasketFactory(site=self.site, owner=UserFactory())
        program = self.mock_program_detail_endpoint(
            self.condition.program_uuid,
            self.site_configuration.discovery_api_url
        )
        for course in program['courses']:
            course_run = Course.objects.get(id=course['course_runs'][0]['key'])
            for seat in course_run.seat_products:
                if seat.attr.id_verification_required:
                    basket.add_product(seat)

        self.mock_user_data(basket.owner.username, mocked_api='enrollments', owned_products=None, response_code=400)
        self.assertTrue(self.condition.is_satisfied(offer, basket))

    def test_is_satisfied_free_basket(self):
        """ Ensure the basket returns False if the basket total is zero. """
        offer = factories.ProgramOfferFactory(partner=self.partner, condition=self.condition)
        basket = BasketFactory(site=self.site, owner=UserFactory())
        test_product = factories.ProductFactory(stockrecords__price_excl_tax=0,
                                                stockrecords__partner__short_code='test')
        basket.add_product(test_product)
        self.assertFalse(self.condition.is_satisfied(offer, basket))

    def test_is_satisfied_site_mismatch(self):
        """ Ensure the condition returns False if the offer partner does not match the basket site partner. """
        offer = factories.ProgramOfferFactory(partner=SiteConfigurationFactory().partner, condition=self.condition)
        basket = BasketFactory(site=self.site, owner=UserFactory())
        basket.add_product(self.test_product)
        self.assertFalse(self.condition.is_satisfied(offer, basket))

    def test_is_satisfied_program_retrieval_failure(self):
        """ The method should return False if no program is retrieved """
        offer = factories.ProgramOfferFactory(partner=self.partner, condition=self.condition)
        basket = BasketFactory(site=self.site, owner=UserFactory())
        basket.add_product(self.test_product)
        self.condition.program_uuid = None
        self.assertFalse(self.condition.is_satisfied(offer, basket))

    @httpretty.activate
    def test_is_satisfied_with_entitlements(self):
        """
        The condition should be satisfied if, for each course in the program, their is either an entitlement sku in the
        basket or the user already has an entitlement for the course and the site has enabled partial program offers.
        """
        offer = factories.ProgramOfferFactory(partner=self.partner, condition=self.condition)
        basket = BasketFactory(site=self.site, owner=UserFactory())
        program = self.mock_program_detail_endpoint(
            self.condition.program_uuid, self.site_configuration.discovery_api_url
        )
        entitlements_response = {
            "count": 0, "num_pages": 1, "current_page": 1, "results": [
                {'mode': 'verified', 'course_uuid': '268afbfc-cc1e-415b-a5d8-c58d955bcfc3'},
                {'mode': 'verified', 'course_uuid': '268afbfc-cc1e-415b-a5d8-c58d955bcfc4'}
            ], "next": None, "start": 0, "previous": None
        }

        # Extract one verified seat for each course
        verified_entitlements = []
        course_uuids = {course['uuid'] for course in program['courses']}
        for parent_entitlement in Product.objects.filter(
                product_class__name=COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME, structure=Product.PARENT
        ):
            for entitlement in Product.objects.filter(parent=parent_entitlement):
                if entitlement.attr.UUID in course_uuids and entitlement.attr.certificate_type == 'verified':
                    verified_entitlements.append(entitlement)

        self.mock_user_data(basket.owner.username, mocked_api='entitlements', owned_products=entitlements_response)
        self.mock_user_data(basket.owner.username)
        # If the user has not added all of the remaining courses in program to their basket,
        # the condition should not be satisfied
        basket.flush()
        for entitlement in verified_entitlements[2:len(verified_entitlements) - 1]:
            basket.add_product(entitlement)
        self.assertFalse(self.condition.is_satisfied(offer, basket))

        # When all courses in the program that the user is not already enrolled in are in their basket
        # and the site allows partial program completion, the condition should be satisfied
        basket.add_product(verified_entitlements[-1])
        self.assertTrue(self.condition.is_satisfied(offer, basket))

        # If the site does not allow partial program completion and the user does not have all of the program
        # courses in their basket, the condition should not be satisfied
        basket.site.siteconfiguration.enable_partial_program = False
        self.assertFalse(self.condition.is_satisfied(offer, basket))

        # Verify the user enrollments are cached
        basket.site.siteconfiguration.enable_partial_program = True
        httpretty.disable()
        with mock.patch('ecommerce.programs.conditions.get_program',
                        return_value=program):
            self.assertTrue(self.condition.is_satisfied(offer, basket))

    @httpretty.activate
    def test_is_satisfied_program_without_entitlements(self):
        """
        User entitlements should not be retrieved if no course in the program has a course entitlement product
        """
        offer = factories.ProgramOfferFactory(partner=self.partner, condition=self.condition)
        basket = BasketFactory(site=self.site, owner=UserFactory())
        program = self.mock_program_detail_endpoint(
            self.condition.program_uuid, self.site_configuration.discovery_api_url, include_entitlements=False
        )
        enrollments = [{'mode': 'verified', 'course_details': {'course_id': 'course-v1:test-org+course+1'}},
                       {'mode': 'verified', 'course_details': {'course_id': 'course-v1:test-org+course+2'}}]
        entitlements_response = {
            "count": 0, "num_pages": 1, "current_page": 1, "results": [
                {'mode': 'verified', 'course_uuid': '268afbfc-cc1e-415b-a5d8-c58d955bcfc3'},
                {'mode': 'verified', 'course_uuid': '268afbfc-cc1e-415b-a5d8-c58d955bcfc4'}
            ], "next": None, "start": 0, "previous": None
        }
        self.mock_user_data(basket.owner.username, owned_products=enrollments)
        self.mock_user_data(basket.owner.username, mocked_api='entitlements', owned_products=entitlements_response)

        for course in program['courses'][2:len(program['courses']) - 1]:
            course_run = Course.objects.get(id=course['course_runs'][0]['key'])
            for seat in course_run.seat_products:
                if seat.attr.id_verification_required:
                    basket.add_product(seat)

        with mock.patch('ecommerce.programs.conditions.deprecated_traverse_pagination') as mock_processing_entitlements:
            self.assertFalse(self.condition.is_satisfied(offer, basket))
            mock_processing_entitlements.assert_not_called()

    @httpretty.activate
    def test_get_lms_resource_for_user_caching_none(self):
        """
        LMS resource should be properly cached when enrollments is None.
        """
        basket = BasketFactory(site=self.site, owner=UserFactory())
        resource_name = 'test_resource_name'
        mock_endpoint = mock.Mock()
        mock_endpoint.get.return_value = None

        return_value = self.condition._get_lms_resource_for_user(basket, resource_name, mock_endpoint)  # pylint: disable=protected-access

        self.assertEqual(return_value, [])
        self.assertEqual(mock_endpoint.get.call_count, 1, 'Endpoint should be called before caching.')

        mock_endpoint.reset_mock()

        return_value = self.condition._get_lms_resource_for_user(basket, resource_name, mock_endpoint)  # pylint: disable=protected-access

        self.assertEqual(return_value, [])
        self.assertEqual(mock_endpoint.get.call_count, 0, 'Endpoint should NOT be called after caching.')

    @httpretty.activate
    def test_is_satisfied_with_non_active_program(self):
        """
        Is satisfied should return false if program is not active.
        """
        offer = factories.ProgramOfferFactory(partner=self.partner, condition=self.condition)
        basket = BasketFactory(site=self.site, owner=UserFactory())
        program = self.mock_program_detail_endpoint(
            self.condition.program_uuid,
            self.site_configuration.discovery_api_url,
            status="retired"
        )
        for course in program['courses']:
            course_run = Course.objects.get(id=course['course_runs'][0]['key'])
            for seat in course_run.seat_products:
                if seat.attr.id_verification_required:
                    basket.add_product(seat)
                    break

        self.assertFalse(self.condition.is_satisfied(offer, basket))
