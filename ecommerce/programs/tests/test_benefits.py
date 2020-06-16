

from ecommerce.extensions.test import factories, mixins
from ecommerce.tests.testcases import TestCase


class AbsoluteDiscountBenefitWithoutRangeTests(mixins.BenefitTestMixin, TestCase):
    factory_class = factories.AbsoluteDiscountBenefitWithoutRangeFactory
    name_format = '{value} fixed-price program discount'


class PercentageDiscountBenefitWithoutRangeTests(mixins.BenefitTestMixin, TestCase):
    factory_class = factories.PercentageDiscountBenefitWithoutRangeFactory
    name_format = '{value}% program discount'
