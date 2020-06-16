

import ddt
from django.template import Context, Template
from oscar.core.loading import get_model
from oscar.test.factories import BenefitFactory

from ecommerce.enterprise.benefits import EnterpriseAbsoluteDiscountBenefit, EnterprisePercentageDiscountBenefit
from ecommerce.extensions.offer.templatetags.offer_tags import benefit_type
from ecommerce.programs.benefits import AbsoluteDiscountBenefitWithoutRange, PercentageDiscountBenefitWithoutRange
from ecommerce.programs.custom import class_path
from ecommerce.tests.testcases import TestCase

Benefit = get_model('offer', 'Benefit')


@ddt.ddt
class OfferTests(TestCase):
    def test_benefit_discount(self):
        benefit = BenefitFactory(type=Benefit.PERCENTAGE, value=35.00)
        template = Template(
            "{% load offer_tags %}"
            "{{ benefit|benefit_discount }}"
        )
        self.assertEqual(template.render(Context({'benefit': benefit})), '35%')

    @ddt.data(
        ({'type': Benefit.PERCENTAGE}, Benefit.PERCENTAGE),
        ({'type': Benefit.FIXED}, Benefit.FIXED),
        ({'type': '', 'proxy_class': class_path(PercentageDiscountBenefitWithoutRange)}, Benefit.PERCENTAGE),
        ({'type': '', 'proxy_class': class_path(AbsoluteDiscountBenefitWithoutRange)}, Benefit.FIXED),
        ({'type': '', 'proxy_class': class_path(EnterprisePercentageDiscountBenefit)}, Benefit.PERCENTAGE),
        ({'type': '', 'proxy_class': class_path(EnterpriseAbsoluteDiscountBenefit)}, Benefit.FIXED),
    )
    @ddt.unpack
    def test_benefit_type(self, factory_kwargs, expected):
        benefit = BenefitFactory(**factory_kwargs)
        self.assertEqual(benefit_type(benefit), expected)
