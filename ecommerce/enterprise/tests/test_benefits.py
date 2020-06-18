

from ecommerce.extensions.test import factories, mixins
from ecommerce.tests.testcases import TestCase


class EnterpriseAbsoluteDiscountBenefitTests(mixins.BenefitTestMixin, TestCase):
    factory_class = factories.EnterpriseAbsoluteDiscountBenefitFactory
    name_format = '{value} fixed-price enterprise discount'


class EnterprisePercentageDiscountBenefitTests(mixins.BenefitTestMixin, TestCase):
    factory_class = factories.EnterprisePercentageDiscountBenefitFactory
    name_format = '{value}% enterprise discount'
