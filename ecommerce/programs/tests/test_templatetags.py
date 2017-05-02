import ddt
from oscar.core.loading import get_model
from oscar.test.factories import BenefitFactory

from ecommerce.programs.benefits import AbsoluteDiscountBenefitWithoutRange, PercentageDiscountBenefitWithoutRange
from ecommerce.programs.custom import class_path
from ecommerce.programs.templatetags.programs import benefit_type
from ecommerce.tests.testcases import TestCase

Benefit = get_model('offer', 'Benefit')


@ddt.ddt
class ProgramOfferTemplateTagTests(TestCase):
    @ddt.data(
        ({'type': Benefit.PERCENTAGE}, Benefit.PERCENTAGE),
        ({'type': Benefit.FIXED}, Benefit.FIXED),
        ({'type': '', 'proxy_class': class_path(PercentageDiscountBenefitWithoutRange)}, Benefit.PERCENTAGE),
        ({'type': '', 'proxy_class': class_path(AbsoluteDiscountBenefitWithoutRange)}, Benefit.FIXED),
    )
    @ddt.unpack
    def test_benefit_type(self, factory_kwargs, expected):
        benefit = BenefitFactory(**factory_kwargs)
        self.assertEqual(benefit_type(benefit), expected)
