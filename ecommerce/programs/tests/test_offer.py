from decimal import Decimal

import httpretty
from oscar.core.loading import get_class

from ecommerce.courses.models import Course
from ecommerce.extensions.partner.strategy import DefaultStrategy
from ecommerce.extensions.test import factories
from ecommerce.programs.tests.mixins import ProgramTestMixin
from ecommerce.tests.testcases import TestCase

Applicator = get_class('offer.utils', 'Applicator')


class ProgramOfferTests(ProgramTestMixin, TestCase):
    """ Verification for program offer application. """

    @httpretty.activate
    def test_offer(self):
        # Our offer is for 100%, so all lines should end up with a price of 0.
        offer = factories.ProgramOfferFactory(benefit=factories.PercentageDiscountBenefitWithoutRangeFactory(value=100))
        basket = factories.BasketFactory(site=self.site, owner=self.create_user())

        program_uuid = offer.condition.program_uuid
        program = self.mock_program_detail_endpoint(program_uuid)

        # Add one course run seat from each course to the basket.
        for course in program['courses']:
            course_run = Course.objects.get(id=course['course_runs'][0]['key'])
            for seat in course_run.seat_products:
                if seat.attr.id_verification_required:
                    basket.add_product(seat)

        # No discounts should be applied, and each line should have a price of 100.00.
        self.assertEqual(len(basket.offer_applications), 0)
        self.assertEqual(basket.total_discount, 0)
        for line in basket.all_lines():
            self.assertEqual(line.line_price_incl_tax_incl_discounts, Decimal(100))

        # Apply the offers as Oscar will in a request
        basket.strategy = DefaultStrategy()
        Applicator().apply(basket, basket.owner)

        # Our discount should be applied, and each line should have a price of 0
        lines = basket.all_lines()
        self.assertEqual(len(basket.offer_applications), 1)
        self.assertEqual(basket.total_discount, Decimal(100) * len(lines))
        for line in lines:
            self.assertEqual(line.line_price_incl_tax_incl_discounts, 0)
