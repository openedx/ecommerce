from ecommerce.extensions.test import factories, mixins
from ecommerce.tests.testcases import TestCase


class JournalAbsoluteDiscountBenefitTests(mixins.BenefitTestMixin, TestCase):
    factory_class = factories.JournalAbsoluteDiscountBenefitFactory
    name_format = '{value} fixed-price journal bundle discount'


class JournalPercentageDiscountBenefitTests(mixins.BenefitTestMixin, TestCase):
    factory_class = factories.JournalPercentageDiscountBenefitFactory
    name_format = '{value}% journal bundle discount'
