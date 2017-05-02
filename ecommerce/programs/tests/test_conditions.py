import httpretty
from oscar.core.loading import get_model

from ecommerce.courses.models import Course
from ecommerce.extensions.test import factories
from ecommerce.programs.tests.mixins import ProgramTestMixin
from ecommerce.tests.testcases import TestCase

Product = get_model('catalogue', 'Product')


class ProgramCourseRunSeatsConditionTests(ProgramTestMixin, TestCase):
    def setUp(self):
        super(ProgramCourseRunSeatsConditionTests, self).setUp()
        self.condition = factories.ProgramCourseRunSeatsConditionFactory()

    def test_name(self):
        """ The name should contain the program's UUID. """
        condition = factories.ProgramCourseRunSeatsConditionFactory()
        expected = 'Basket contains a seat for every course in program {}'.format(condition.program_uuid)
        self.assertEqual(condition.name, expected)

    @httpretty.activate
    def test_get_program(self):
        """ The method should return data from the Catalog Service API. Data should be cached for subsequent calls. """
        data = self.mock_program_detail_endpoint(self.condition.program_uuid)
        self.assertEqual(self.condition.get_program(self.site.siteconfiguration), data)

        # The program data should be cached
        httpretty.disable()
        self.assertEqual(self.condition.get_program(self.site.siteconfiguration), data)

    @httpretty.activate
    def test_is_satisfied(self):
        """ The method should return True if the basket contains one course run seat corresponding to each
        course in the program. """
        offer = factories.ProgramOfferFactory(condition=self.condition)
        basket = factories.BasketFactory(site=self.site)
        program = self.mock_program_detail_endpoint(self.condition.program_uuid)

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
        for verified_seat in verified_seats[:len(verified_seats) - 1]:
            basket.add_product(verified_seat)
        self.assertFalse(self.condition.is_satisfied(offer, basket))

        # The condition should be satisfied if one valid course run from each course is in the basket.
        basket.add_product(verified_seats[len(verified_seats) - 1])
        self.assertTrue(self.condition.is_satisfied(offer, basket))
