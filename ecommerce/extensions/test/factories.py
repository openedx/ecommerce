from oscar.test.factories import *  # pylint:disable=wildcard-import,unused-wildcard-import

from ecommerce.extensions.api.v2.views.coupons import CouponViewSet
from ecommerce.tests.factories import PartnerFactory

Benefit = get_model('offer', 'Benefit')
Catalog = get_model('catalogue', 'Catalog')
Voucher = get_model('voucher', 'Voucher')

OrderNumberGenerator = get_class('order.utils', 'OrderNumberGenerator')


def create_order(number=None, basket=None, user=None, shipping_address=None,  # pylint:disable=function-redefined
                 shipping_method=None, billing_address=None, total=None, **kwargs):
    """
    Helper method for creating an order for testing
    """
    if not basket:
        basket = Basket.objects.create()
        basket.strategy = strategy.Default()
        product = create_product()
        create_stockrecord(
            product, num_in_stock=10, price_excl_tax=D('10.00'))
        basket.add_product(product)
    if not basket.id:
        basket.save()
    if shipping_method is None:
        shipping_method = Free()
    shipping_charge = shipping_method.calculate(basket)
    if total is None:
        total = OrderTotalCalculator().calculate(basket, shipping_charge)

    # Ensure we use our own OrderNumberGenerator instead of Oscar's default.
    number = number or OrderNumberGenerator().order_number(basket)

    order = OrderCreator().place_order(
        order_number=number,
        user=user,
        basket=basket,
        shipping_address=shipping_address,
        shipping_method=shipping_method,
        shipping_charge=shipping_charge,
        billing_address=billing_address,
        total=total,
        **kwargs)
    basket.set_as_submitted()
    return order


def create_coupon(
        title='Test coupon',
        price=100,
        partner=None,
        catalog=None,
        code='',
        benefit_value=100,
        sub_category=''
    ):
    """Helper method for creating a coupon."""
    if partner is None:
        partner = PartnerFactory(name='Tester')
    if catalog is None:
        catalog = Catalog.objects.create(partner=partner)
    quantity = 5
    if code is not '':
        quantity = 1
    data = {
        'partner': partner,
        'benefit_type': Benefit.PERCENTAGE,
        'benefit_value': benefit_value,
        'catalog': catalog,
        'end_date': datetime.date(2020, 1, 1),
        'code': code,
        'quantity': quantity,
        'start_date': datetime.date(2015, 1, 1),
        'voucher_type': Voucher.SINGLE_USE,
        'category': 'Test category',
        'sub_category': sub_category
    }

    coupon = CouponViewSet().create_coupon_product(
        title=title,
        price=price,
        data=data
    )
    return coupon
