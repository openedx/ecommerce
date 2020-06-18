"""
Tests for the ecommerce.enterprise.mixins module.
"""


from decimal import Decimal

import ddt
from oscar.core.loading import get_model
from oscar.test import factories

from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.enterprise.mixins import EnterpriseDiscountMixin
from ecommerce.enterprise.tests.mixins import EnterpriseDiscountTestMixin
from ecommerce.extensions.payment.models import EnterpriseContractMetadata
from ecommerce.extensions.test.factories import create_order
from ecommerce.tests.factories import UserFactory
from ecommerce.tests.testcases import TestCase

Catalog = get_model('catalogue', 'Catalog')


@ddt.ddt
class EnterpriseDiscountMixinTests(EnterpriseDiscountTestMixin, TestCase):
    """
    Tests validating generic behaviors of the EnterpriseDiscountMixin.
    """

    def setUp(self):
        super(EnterpriseDiscountMixinTests, self).setUp()
        course = CourseFactory(id='edX/DemoX/Demo_Course', name='Demo Course', partner=self.partner)
        user = UserFactory()
        basket = factories.BasketFactory(owner=user, site=self.site)
        basket.add_product(
            course.create_or_update_seat('test-certificate-type', False, 100, None),
            1
        )
        self.order = create_order(number=1, basket=basket, user=user)

    def test_get_enterprise_customer_cost_for_line(self):
        """
        Test correct values for discount percentage are evaluated and rounded.
        """
        line_price = Decimal('199.00')
        effective_discount_percentage = Decimal('0.001027742658353086344768502165')

        # pylint: disable=protected-access
        actual = EnterpriseDiscountMixin._get_enterprise_customer_cost_for_line(
            line_price, effective_discount_percentage
        )
        expected = Decimal('198.79548')
        self.assertEqual(actual, expected)

    def test_calculate_effective_discount_percentage_fixed(self):
        """
        Test correct values for discount percentage are evaluated when discount type is FIXED.
        """
        enterprise_contract_metadata = EnterpriseContractMetadata(
            discount_type=EnterpriseContractMetadata.FIXED,
            discount_value=Decimal('12.3456'),
            amount_paid=Decimal('12000.00')
        )
        # pylint: disable=protected-access
        actual = EnterpriseDiscountMixin._calculate_effective_discount_percentage(enterprise_contract_metadata)
        expected = Decimal('12.3456') / (Decimal('12.3456') + Decimal('12000.00'))
        self.assertEqual(actual, expected)

    def test_calculate_effective_discount_percentage_percentage(self):
        """
        Test correct values for discount percentage are evaluated when discount type is PERCENTAGE.
        """
        enterprise_contract_metadata = EnterpriseContractMetadata(
            discount_type=EnterpriseContractMetadata.PERCENTAGE,
            discount_value=Decimal('12.3456'),
            amount_paid=Decimal('12000.00')
        )
        # pylint: disable=protected-access
        actual = EnterpriseDiscountMixin._calculate_effective_discount_percentage(enterprise_contract_metadata)
        expected = Decimal('.123456')
        self.assertEqual(actual, expected)

    def assert_enterprise_discount_fields(
            self,
            line,
            expected_effective_contract_discount_percentage,
            expected_effective_contract_discounted_price,
            discount_percentage=None,
            is_manual_order=False
    ):
        """
        Assert the enterprise discount fields.
        """
        # field are None before update.
        assert line.effective_contract_discount_percentage is None
        assert line.effective_contract_discounted_price is None

        EnterpriseDiscountMixin().update_orderline_with_enterprise_discount_metadata(
            self.order,
            line,
            discount_percentage=discount_percentage,
            is_manual_order=is_manual_order
        )

        # field have expected values after update
        self.assertEqual(line.effective_contract_discount_percentage, expected_effective_contract_discount_percentage)
        self.assertEqual(line.effective_contract_discounted_price, expected_effective_contract_discounted_price)

    @ddt.unpack
    @ddt.data(
        # Test with order's voucher discount
        {
            'amount_paid': Decimal('40'),
            'discount_value': Decimal('30'),
            'discount_type': EnterpriseContractMetadata.PERCENTAGE,
            'is_manual_order': False,
            'create_order_discount_callback': 'create_order_voucher_discount',
            'expected_effective_contract_discount_percentage': Decimal('0.3'),
            'expected_effective_contract_discounted_price': Decimal('70.0000'),
        },
        # Test with order's offer discount
        {
            'amount_paid': Decimal('100'),
            'discount_value': Decimal('100'),
            'discount_type': EnterpriseContractMetadata.FIXED,
            'is_manual_order': False,
            'create_order_discount_callback': 'create_order_offer_discount',
            'expected_effective_contract_discount_percentage': Decimal('0.5'),
            'expected_effective_contract_discounted_price': Decimal('50.0000'),
        },
        # Test with manual order's discount.
        {
            'amount_paid': Decimal('100'),
            'discount_value': Decimal('20'),
            'discount_type': EnterpriseContractMetadata.PERCENTAGE,
            'is_manual_order': True,
            'create_order_discount_callback': None,
            'expected_effective_contract_discount_percentage': Decimal('0.20'),
            'expected_effective_contract_discounted_price': Decimal('80.0000'),
        },
        # Test with no order discount
        {
            'amount_paid': None,
            'discount_value': None,
            'discount_type': None,
            'is_manual_order': False,
            'create_order_discount_callback': None,
            'expected_effective_contract_discount_percentage': None,
            'expected_effective_contract_discounted_price': None,
        },
    )
    def test_update_orderline_with_enterprise_discount(
            self,
            amount_paid,
            discount_value,
            discount_type,
            is_manual_order,
            create_order_discount_callback,
            expected_effective_contract_discount_percentage,
            expected_effective_contract_discounted_price
    ):
        """
        Test update_orderline_with_enterprise_discount method with different order discounts.
        """
        if not is_manual_order and create_order_discount_callback is not None:
            # Creating order discount
            getattr(self, create_order_discount_callback)(
                self.order,
                enterprise_contract_metadata=EnterpriseContractMetadata.objects.create(
                    discount_type=discount_type,
                    discount_value=discount_value,
                    amount_paid=amount_paid
                )
            )

        line = self.order.lines.all().first()

        self.assert_enterprise_discount_fields(
            line,
            discount_percentage=discount_value,
            is_manual_order=is_manual_order,
            expected_effective_contract_discount_percentage=expected_effective_contract_discount_percentage,
            expected_effective_contract_discounted_price=expected_effective_contract_discounted_price
        )
