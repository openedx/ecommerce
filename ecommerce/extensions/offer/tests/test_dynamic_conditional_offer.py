
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
from oscar.test.factories import BasketFactory
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin

from ecommerce.extensions.offer.constants import DYNAMIC_DISCOUNT_FLAG
from ecommerce.tests.factories import ProductFactory, SiteConfigurationFactory
from ecommerce.tests.mixins import Applicator

from waffle.testutils import override_flag

ConditionalOffer = get_model('offer', 'ConditionalOffer')
LOGGER_NAME = 'ecommerce.programs.conditions'

def _mock_jwt_decode_handler(jwt):
    return jwt

@ddt.ddt
class DynamicPercentageDiscountBenefitTests(mixins.BenefitTestMixin, TestCase):
    factory_class = factories.DynamicPercentageDiscountBenefitFactory
    name_format = 'dynamic_discount_benefit'

    @override_flag(DYNAMIC_DISCOUNT_FLAG, active=True)
    @patch('crum.get_current_request')
    @patch('ecommerce.extensions.offer.dynamic_conditional_offer.jwt_decode_handler', side_effect=_mock_jwt_decode_handler)
    @ddt.data(10, 15, 20)
    def test_apply(self, discount_percent, jwt_decode_handler, request):
        discount_jwt = {'discount_applicable':True, 'discount_percent':discount_percent}
        request.return_value = Mock(method='GET', GET={'discount_jwt': discount_jwt})

        basket = BasketFactory(site=self.site, owner=self.create_user())

        product = ProductFactory(categories=[], stockrecords__price_currency='USD')
        basket.add_product(product)
        Applicator().apply(basket)

        # Our discount should be applied
        lines = basket.all_lines()
        self.assertEqual(len(basket.offer_applications), 1)
        benefit = basket.offer_discounts[0].get('offer').benefit
        self.assertEqual(
            basket.total_discount, 
            benefit.round(
                discount_jwt['discount_percent']/Decimal('100') * basket.total_incl_tax_excl_discounts))



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


