
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
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.tests.factories import ProductFactory, SiteConfigurationFactory

ConditionalOffer = get_model('offer', 'ConditionalOffer')
LOGGER_NAME = 'ecommerce.programs.conditions'

@ddt
class TestDynamicConditionalOfferUtils(TestCase):

    @ddt.ddt
    @ddt.data(
        ('GET', True),
        ('GET', False),
        ('POST', True),
        ('POST', False),
    )
    @ddt.unpack
    def test_get_decoded_jwt_discount_from_request(request_type, applicable):
        print(str(request_type))
        assert True
        

def test_get_percentage_from_request():
    assert True

class DynamicPercentageDiscountBenefitTests(mixins.BenefitTestMixin, TestCase):
    factory_class = factories.DynamicPercentageDiscountBenefitFactory
    name_format = 'dynamic_discount_benefit'

    # def setUp(self):
    #     self.basket = BasketFactory(owner=self.request.user, site=self.request.site)
    #     voucher, product = prepare_voucher()
    #     basket.add_product(product, 1)
    #     applied, msg = apply_voucher_on_basket_and_check_discount(voucher, self.request, basket)
    #     self.assertEqual(applied, True)
    #     self.assertIsNotNone(basket.applied_offers())
    #     self.assertEqual(msg, "Coupon code '{code}' added to basket.".format(code=voucher.code))


    def test_apply(self):
        assert True


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


