# -*- coding: utf-8 -*-
"""Broadly-useful factory methods for use in automated tests."""
from decimal import Decimal
import factory

from oscar.test.factories import *  # pylint: disable=unused-wildcard-import, function-redefined, wildcard-import
from oscar.test.newfactories import *  # pylint: disable=unused-wildcard-import, function-redefined, wildcard-import

from ecommerce.extensions.refund.status import REFUND, REFUND_LINE


class PartnerFactory(PartnerFactory):  # pylint: disable=function-redefined
    short_code = factory.Sequence(int)


class BasketFactory(BasketFactory):  # pylint: disable=function-redefined
    partner = factory.SubFactory(PartnerFactory)


# pylint: disable=function-redefined
def create_order(number=None, basket=None, user=None, shipping_address=None,
                 shipping_method=None, billing_address=None, total=None, **kwargs):
    """Helper method for creating an order for testing. Using basket factory to
    fix the partner-id exception.
    """
    if not basket:
        basket = BasketFactory()
        product = create_product()
        create_stockrecord(product, num_in_stock=10, price_excl_tax=D('10.00'))
        basket.add_product(product)
    if not basket.id:
        basket.save()
    if shipping_method is None:
        shipping_method = Free()
    shipping_charge = shipping_method.calculate(basket)
    if total is None:
        total = OrderTotalCalculator().calculate(basket, shipping_charge)
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


def create_basket(empty=False):  # pylint: disable=function-redefined
    """Using basket factory to fix the partner-id exception."""
    basket = BasketFactory()
    if not empty:
        product = create_product()
        create_stockrecord(product, num_in_stock=2)
        basket.add_product(product)
    return basket


class RefundFactory(factory.DjangoModelFactory):
    status = getattr(settings, 'OSCAR_INITIAL_REFUND_STATUS', REFUND.OPEN)
    user = factory.SubFactory(UserFactory)
    total_credit_excl_tax = Decimal(1.00)

    @factory.lazy_attribute
    def order(self):
        return create_order(user=self.user)

    @factory.post_generation
    def create_lines(self, create, extracted, **kwargs):  # pylint: disable=unused-argument
        if not create:
            return

        for line in self.order.lines.all():
            RefundLineFactory.create(refund=self, order_line=line)

        self.total_credit_excl_tax = sum([line.line_credit_excl_tax for line in self.lines.all()])
        self.save()

    class Meta(object):
        model = get_model('refund', 'Refund')


class RefundLineFactory(factory.DjangoModelFactory):
    status = getattr(settings, 'OSCAR_INITIAL_REFUND_LINE_STATUS', REFUND_LINE.OPEN)
    refund = factory.SubFactory(RefundFactory)
    line_credit_excl_tax = Decimal(1.00)

    @factory.lazy_attribute
    def order_line(self):
        order = create_order()
        return order.lines.first()

    class Meta(object):
        model = get_model('refund', 'RefundLine')


class OrderFactory(OrderFactory):
    basket = factory.SubFactory(BasketFactory)
