from django.template import Context, Template
from oscar.core.loading import get_model
from oscar.test.factories import BenefitFactory

from ecommerce.tests.testcases import TestCase

Benefit = get_model('offer', 'Benefit')


class OfferTests(TestCase):
    def test_benefit_discount(self):
        benefit = BenefitFactory(type=Benefit.PERCENTAGE, value=35.00)
        template = Template(
            "{% load offer_tags %}"
            "{{ benefit|benefit_discount }}"
        )
        self.assertEqual(template.render(Context({'benefit': benefit})), '35%')
