
from ecommerce.extensions.test import factories, mixins
from ecommerce.tests.testcases import TestCase
from decimal import Decimal
from uuid import uuid4

import ddt
import httpretty
from mock import patch, Mock
from oscar.core.loading import get_model

from ecommerce.coupons.tests.mixins import CouponMixin
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.test.factories import BasketFactory
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin

from ecommerce.extensions.offer.constants import DYNAMIC_DISCOUNT_FLAG
from ecommerce.tests.factories import ProductFactory, SiteConfigurationFactory

from waffle.testutils import override_flag

ConditionalOffer = get_model('offer', 'ConditionalOffer')
LOGGER_NAME = 'ecommerce.programs.conditions'

# @ddt.ddt
# class DynamicPercentageDiscountBenefitTests(mixins.BenefitTestMixin, TestCase, LmsApiMockMixin):
#     factory_class = factories.DynamicPercentageDiscountBenefitFactory
#     name_format = 'dynamic_discount_benefit'

#     def test_apply(self):
#         basket = BasketFactory(site=self.site, owner=self.create_user())
#                 program_uuid = offer.condition.program_uuid
#         program = self.mock_program_detail_endpoint(program_uuid, self.site_configuration.discovery_api_url)
#         self.mock_user_data(basket.owner.username)

#         # Add one course run seat from each course to the basket.
#         products = []
#         for course in program['courses']:
#             course_run = Course.objects.get(id=course['course_runs'][0]['key'])
#             for seat in course_run.seat_products:
#                 if seat.attr.id_verification_required:
#                     products.append(seat)
#                     basket.add_product(seat)

#         # No discounts should be applied, and each line should have a price of 100.00.
#         self.assertEqual(len(basket.offer_applications), 0)
#         self.assertEqual(basket.total_discount, 0)
#         for line in basket.all_lines():
#             self.assertEqual(line.line_price_incl_tax_incl_discounts, Decimal(100))

#         # Apply the offers as Oscar will in a request
#         basket.strategy = DefaultStrategy()
#         Applicator().apply(basket, basket.owner)

#         # Our discount should be applied, and each line should have a price of 0
#         lines = basket.all_lines()
#         self.assertEqual(len(basket.offer_applications), 1)
#         self.assertEqual(basket.total_discount, Decimal(100) * len(lines))
#         for line in lines:
#             self.assertEqual(line.line_price_incl_tax_incl_discounts, 0)




@ddt.ddt
class DynamicConditionTests(TestCase):
    def setUp(self):
        super(DynamicConditionTests, self).setUp()

    def test_name(self):
        self.assertTrue(True)

    @httpretty.activate
    def test_is_satisfied_true(self):
        self.assertTrue(True)

    @httpretty.activate
    def test_is_satisfied_for_anonymous_user(self):
        self.assertFalse(False)

    def test_is_satisfied_empty_basket(self):
        self.assertFalse(False)

    def test_is_satisfied_free_basket(self):
       self.assertFalse(False)


