

from decimal import Decimal

import ddt
from mock import Mock, patch
from oscar.core.loading import get_model
from oscar.test.factories import BasketFactory
from waffle.testutils import override_flag

from ecommerce.extensions.offer.constants import DYNAMIC_DISCOUNT_FLAG
from ecommerce.extensions.test.factories import DynamicPercentageDiscountBenefitFactory
from ecommerce.extensions.test.mixins import BenefitTestMixin
from ecommerce.tests.factories import ProductFactory
from ecommerce.tests.mixins import Applicator
from ecommerce.tests.testcases import TestCase

Condition = get_model('offer', 'Condition')
ConditionalOffer = get_model('offer', 'ConditionalOffer')
LOGGER_NAME = 'ecommerce.programs.conditions'


def _mock_jwt_decode_handler(jwt):
    return jwt


@ddt.ddt
class DynamicPercentageDiscountBenefitTests(BenefitTestMixin, TestCase):
    """
    Tests to make sure that the dynamic percentage discount benefit results in the correct discount
    """
    factory_class = DynamicPercentageDiscountBenefitFactory
    name_format = 'dynamic_discount_benefit'

    @override_flag(DYNAMIC_DISCOUNT_FLAG, active=True)
    @patch('crum.get_current_request')
    @patch('ecommerce.extensions.offer.dynamic_conditional_offer.jwt_decode_handler',
           side_effect=_mock_jwt_decode_handler)
    @ddt.data(
        ('GET', 10),
        ('GET', 15),
        ('GET', 20),
        ('GET', None),
        ('POST', 10),
        ('POST', 15),
        ('POST', 20),
        ('POST', None)
    )
    def test_apply(self, discount_param, jwt_decode_handler, request):  # pylint: disable=unused-argument
        request_type = discount_param[0]
        discount_percent = discount_param[1]
        discount_jwt = {'discount_applicable': True, 'discount_percent': discount_percent}
        mock_kwargs = {'method': request_type, request_type: {'discount_jwt': discount_jwt}}
        request.return_value = Mock(**mock_kwargs)
        basket = BasketFactory(site=self.site, owner=self.create_user())

        product = ProductFactory(categories=[], stockrecords__price_currency='USD')
        basket.add_product(product)
        Applicator().apply(basket)

        if discount_percent is not None:
            # Our discount should be applied
            self.assertEqual(len(basket.offer_applications), 1)
            benefit = basket.offer_discounts[0].get('offer').benefit
            self.assertEqual(
                basket.total_discount,
                benefit.round(
                    discount_jwt['discount_percent'] / Decimal('100') * basket.total_incl_tax_excl_discounts))
        else:
            self.assertEqual(len(basket.offer_applications), 0)


@ddt.ddt
class DynamicConditionTests(TestCase):
    """
    Tests to make sure that the dynamic discount condition correctly compute whether to give a discount
    """

    def setUp(self):
        super(DynamicConditionTests, self).setUp()
        self.condition = Condition.objects.get(
            proxy_class='ecommerce.extensions.offer.dynamic_conditional_offer.DynamicDiscountCondition').proxy()
        self.offer = ConditionalOffer.objects.get(name='dynamic_conditional_offer')
        self.basket = BasketFactory(site=self.site, owner=self.create_user())

    def test_name(self):
        self.assertTrue(self.condition.name == 'dynamic_discount_condition')

    @override_flag(DYNAMIC_DISCOUNT_FLAG, active=True)
    @patch('crum.get_current_request')
    @patch('ecommerce.extensions.offer.dynamic_conditional_offer.jwt_decode_handler',
           side_effect=_mock_jwt_decode_handler)
    @ddt.data(
        {'discount_applicable': True, 'discount_percent': 15},
        {'discount_applicable': False, 'discount_percent': 15},
        None,)
    def test_is_satisfied_true(self, discount_jwt, jwt_decode_handler, request):   # pylint: disable=unused-argument
        request.return_value = Mock(method='GET', GET={'discount_jwt': discount_jwt})
        product = ProductFactory(stockrecords__price_excl_tax=10, categories=[])
        self.basket.add_product(product)
        if discount_jwt and discount_jwt.get('discount_applicable') is True:
            self.assertTrue(self.condition.is_satisfied(self.offer, self.basket))
        else:
            self.assertFalse(self.condition.is_satisfied(self.offer, self.basket))

    @override_flag(DYNAMIC_DISCOUNT_FLAG, active=True)
    @patch('crum.get_current_request')
    def test_is_satisfied_quantity_more_than_1(self, request):   # pylint: disable=unused-argument
        """
        This discount should not apply if are buying more than one of the same course.
        """
        product = ProductFactory(stockrecords__price_excl_tax=10, categories=[])
        self.basket.add_product(product, quantity=2)
        self.assertFalse(self.condition.is_satisfied(self.offer, self.basket))
