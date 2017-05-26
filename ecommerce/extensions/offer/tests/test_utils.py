from decimal import Decimal

import ddt
from oscar.core.loading import get_model

from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.extensions.checkout.utils import add_currency
from ecommerce.extensions.offer.utils import _remove_exponent_and_trailing_zeros, format_benefit_value
from ecommerce.extensions.test.factories import *  # pylint:disable=wildcard-import,unused-wildcard-import
from ecommerce.tests.testcases import TestCase

Benefit = get_model('offer', 'Benefit')


@ddt.ddt
class UtilTests(CourseCatalogTestMixin, TestCase):

    def setUp(self):
        super(UtilTests, self).setUp()
        self.course = CourseFactory()
        self.verified_seat = self.course.create_or_update_seat('verified', False, 100, self.partner)
        self.stock_record = StockRecord.objects.filter(product=self.verified_seat).first()
        self.seat_price = self.stock_record.price_excl_tax
        self._range = RangeFactory(products=[self.verified_seat, ])

        self.percentage_benefit = BenefitFactory(type=Benefit.PERCENTAGE, range=self._range, value=35.00)
        self.value_benefit = BenefitFactory(type=Benefit.FIXED, range=self._range, value=self.seat_price - 10)

    def test_format_benefit_value(self):
        """ format_benefit_value(benefit) should format benefit value based on benefit type """
        benefit_value = format_benefit_value(self.percentage_benefit)
        self.assertEqual(benefit_value, '35%')

        benefit_value = format_benefit_value(self.value_benefit)
        expected_benefit = add_currency(Decimal((self.seat_price - 10)))
        self.assertEqual(benefit_value, '${expected_benefit}'.format(expected_benefit=expected_benefit))

    def test_format_program_benefit_value(self):
        """ format_benefit_value(program_benefit) should format benefit value based on proxy class. """
        percentage_benefit = PercentageDiscountBenefitWithoutRangeFactory()
        benefit_value = format_benefit_value(percentage_benefit)
        self.assertEqual(benefit_value, '{}%'.format(percentage_benefit.value))

        absolute_benefit = AbsoluteDiscountBenefitWithoutRangeFactory()
        benefit_value = format_benefit_value(absolute_benefit)
        expected_value = add_currency(Decimal(absolute_benefit.value))
        self.assertEqual(benefit_value, '${}'.format(expected_value))

    @ddt.data(
        ('1.0', '1'),
        ('5000.0', '5000'),
        ('1.45000', '1.45'),
        ('5000.40000', '5000.4'),
    )
    @ddt.unpack
    def test_remove_exponent_and_trailing_zeros(self, value, expected):
        """
        _remove_exponent_and_trailing_zeros(decimal) should remove exponent and trailing zeros
        from decimal number
        """
        decimal = _remove_exponent_and_trailing_zeros(Decimal(value))
        self.assertEqual(decimal, Decimal(expected))
