import ddt
import httpretty
import mock
from oscar.core.loading import get_model

from requests import Timeout
from slumber.exceptions import HttpNotFoundError, SlumberBaseException

from ecommerce.courses.models import Course
from ecommerce.extensions.test import factories
from ecommerce.programs.tests.mixins import ProgramTestMixin
from ecommerce.tests.factories import ProductFactory
from ecommerce.tests.testcases import TestCase

Product = get_model('catalogue', 'Product')
LOGGER_NAME = 'ecommerce.programs.conditions'


@ddt.ddt
class ProgramCourseRunSeatsConditionTests(ProgramTestMixin, TestCase):
    def setUp(self):
        super(ProgramCourseRunSeatsConditionTests, self).setUp()
        self.condition = factories.ProgramCourseRunSeatsConditionFactory()
        self.test_product = ProductFactory(stockrecords__price_excl_tax=10)
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
        offer = factories.ProgramOfferFactory(condition=self.condition)
        basket = factories.BasketFactory(site=self.site, owner=factories.UserFactory())
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

        self.mock_enrollment_api(basket.owner.username)
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
        offer = factories.ProgramOfferFactory(condition=self.condition)
        basket = factories.BasketFactory(site=self.site, owner=factories.UserFactory())
        program = self.mock_program_detail_endpoint(
            self.condition.program_uuid, self.site_configuration.discovery_api_url
        )
        enrollments = [{'mode': 'verified', 'course_details': {'course_id': 'course-v1:test-org+course+1'}},
                       {'mode': 'verified', 'course_details': {'course_id': 'course-v1:test-org+course+2'}}]

        # Extract one verified seat for each course
        verified_seats = []
        for course in program['courses']:
            course_run = Course.objects.get(id=course['course_runs'][0]['key'])
            for seat in course_run.seat_products:
                if seat.attr.id_verification_required:
                    verified_seats.append(seat)

        self.mock_enrollment_api(basket.owner.username, enrollments=enrollments)
        # If the user has not added all of the remaining courses in program to their basket,
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
    def test_is_satisfied_with_exception(self, value):
        """ The method should return False if there is an exception when trying to get program details. """
        offer = factories.ProgramOfferFactory(condition=self.condition)
        basket = factories.BasketFactory(site=self.site, owner=factories.UserFactory())
        basket.add_product(self.test_product)

        with mock.patch('ecommerce.programs.conditions.get_program',
                        side_effect=value):
            self.assertFalse(self.condition.is_satisfied(offer, basket))

    def test_is_satisfied_free_basket(self):
        """ Ensure the basket returns False if the basket total is zero. """
        offer = factories.ProgramOfferFactory(condition=self.condition)
        basket = factories.BasketFactory(site=self.site, owner=factories.UserFactory())
        test_product = factories.ProductFactory(stockrecords__price_excl_tax=0,
                                                stockrecords__partner__short_code='test')
        basket.add_product(test_product)
        self.assertFalse(self.condition.is_satisfied(offer, basket))

    def test_is_satisfied_program_retrieval_failure(self):
        """ The method should return False if no program is retrieved """
        offer = factories.ProgramOfferFactory(condition=self.condition)
        basket = factories.BasketFactory(site=self.site, owner=factories.UserFactory())
        basket.add_product(self.test_product)
        self.condition.program_uuid = None
        self.assertFalse(self.condition.is_satisfied(offer, basket))
