import uuid
from datetime import datetime

import factory
from django.utils.timezone import now
from oscar.test.factories import ConditionalOfferFactory as BaseConditionalOfferFactory
from oscar.test.factories import VoucherFactory as BaseVoucherFactory
from oscar.test.factories import *  # pylint:disable=wildcard-import,unused-wildcard-import

from ecommerce.programs.benefits import AbsoluteDiscountBenefitWithoutRange, PercentageDiscountBenefitWithoutRange
from ecommerce.programs.conditions import ProgramCourseRunSeatsCondition
from ecommerce.programs.custom import class_path

Benefit = get_model('offer', 'Benefit')
Catalog = get_model('catalogue', 'Catalog')
ConditionalOffer = get_model('offer', 'ConditionalOffer')
Default = get_class('partner.strategy', 'Default')
Voucher = get_model('voucher', 'Voucher')

OrderNumberGenerator = get_class('order.utils', 'OrderNumberGenerator')


def create_order(number=None, basket=None, user=None, shipping_address=None,  # pylint:disable=function-redefined
                 shipping_method=None, billing_address=None, total=None, **kwargs):
    """
    Helper function for creating an order for testing
    """
    if not basket:
        basket = Basket.objects.create()
        basket.strategy = Default()
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


def prepare_voucher(code='COUPONTEST', _range=None, start_datetime=None, end_datetime=None, benefit_value=100,
                    benefit_type=Benefit.PERCENTAGE, usage=Voucher.SINGLE_USE, max_usage=None, email_domains=None,
                    enterprise_customer=None):
    """ Helper function to create a voucher and add an offer to it that contains a product. """

    # NOTE (CCB): We use empty categories here to avoid unique-constraint issues that occur when we use
    # ProductCategoryFactory in conjunction with pre-created Category objects.
    if _range is None:
        product = ProductFactory(categories=[])
        _range = RangeFactory(products=[product], enterprise_customer=enterprise_customer)
    elif _range.num_products() > 0:
        product = _range.all_products()[0]
    else:
        product = ProductFactory(categories=[])

    if start_datetime is None:
        start_datetime = now() - datetime.timedelta(days=1)

    if end_datetime is None:
        end_datetime = now() + datetime.timedelta(days=10)

    voucher = VoucherFactory(
        code=code,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        usage=usage
    )
    benefit = BenefitFactory(type=benefit_type, range=_range, value=benefit_value)
    condition = ConditionFactory(value=1, range=_range)
    if max_usage:
        offer = ConditionalOfferFactory(
            offer_type=ConditionalOffer.VOUCHER,
            benefit=benefit,
            condition=condition,
            max_global_applications=max_usage,
            email_domains=email_domains
        )
    else:
        offer = ConditionalOfferFactory(
            offer_type=ConditionalOffer.VOUCHER,
            benefit=benefit,
            condition=condition,
            email_domains=email_domains
        )
    voucher.offers.add(offer)
    return voucher, product


class VoucherFactory(BaseVoucherFactory):  # pylint: disable=function-redefined
    name = factory.Faker('word')
    code = factory.Sequence(lambda n: 'VOUCHERCODE{number}'.format(number=n))


class ConditionalOfferFactory(BaseConditionalOfferFactory):  # pylint: disable=function-redefined
    name = factory.Sequence(lambda n: 'ConditionalOffer {number}'.format(number=n))


class AbsoluteDiscountBenefitWithoutRangeFactory(BenefitFactory):
    range = None
    type = ''
    value = 10
    proxy_class = class_path(AbsoluteDiscountBenefitWithoutRange)


class PercentageDiscountBenefitWithoutRangeFactory(BenefitFactory):
    range = None
    type = ''
    value = 10
    proxy_class = class_path(PercentageDiscountBenefitWithoutRange)


class ProgramCourseRunSeatsConditionFactory(ConditionFactory):
    range = None
    type = ''
    value = None
    program_uuid = factory.LazyFunction(uuid.uuid4)
    proxy_class = class_path(ProgramCourseRunSeatsCondition)

    class Meta(object):
        model = ProgramCourseRunSeatsCondition


class ProgramOfferFactory(ConditionalOfferFactory):
    benefit = factory.SubFactory(PercentageDiscountBenefitWithoutRangeFactory)
    condition = factory.SubFactory(ProgramCourseRunSeatsConditionFactory)
    max_basket_applications = 1
    offer_type = ConditionalOffer.SITE
    status = ConditionalOffer.OPEN
