import uuid
from datetime import datetime

import factory
from django.utils.timezone import now
from oscar.test.factories import ConditionalOfferFactory as BaseConditionalOfferFactory
from oscar.test.factories import VoucherFactory as BaseVoucherFactory
from oscar.test.factories import *  # pylint:disable=wildcard-import,unused-wildcard-import

from ecommerce.enterprise.benefits import BENEFIT_MAP as ENTERPRISE_BENEFIT_MAP
from ecommerce.enterprise.benefits import EnterpriseAbsoluteDiscountBenefit, EnterprisePercentageDiscountBenefit
from ecommerce.enterprise.conditions import EnterpriseCustomerCondition
from ecommerce.extensions.offer.models import OFFER_PRIORITY_ENTERPRISE, OFFER_PRIORITY_VOUCHER
# TODO: journals dependency
from ecommerce.journals.benefits import JournalBundleAbsoluteDiscountBenefit, JournalBundlePercentageDiscountBenefit
from ecommerce.journals.conditions import JournalBundleCondition
from ecommerce.programs.benefits import AbsoluteDiscountBenefitWithoutRange, PercentageDiscountBenefitWithoutRange
from ecommerce.programs.conditions import ProgramCourseRunSeatsCondition
from ecommerce.programs.custom import class_path
from ecommerce.tests.factories import SiteConfigurationFactory

Benefit = get_model('offer', 'Benefit')
Catalog = get_model('catalogue', 'Catalog')
ConditionalOffer = get_model('offer', 'ConditionalOffer')
Default = get_class('partner.strategy', 'Default')
ProductClass = get_model('catalogue', 'ProductClass')
Voucher = get_model('voucher', 'Voucher')

OrderNumberGenerator = get_class('order.utils', 'OrderNumberGenerator')


def create_basket(owner=None, site=None, empty=False, price='10.00', product_class=None):  # pylint:disable=function-redefined
    if site is None:
        site = SiteConfigurationFactory().site
    if owner is None:
        owner = UserFactory()
    basket = Basket.objects.create(site=site, owner=owner)
    basket.strategy = Default()
    if not empty:
        if product_class:
            product_class_instance = ProductClass.objects.get(name=product_class)
            product = create_product(product_class=product_class_instance)
        else:
            product = create_product()
        create_stockrecord(product, num_in_stock=2, price_excl_tax=D(price))
        basket.add_product(product)
    return basket


def create_order(number=None, basket=None, user=None, shipping_address=None,  # pylint:disable=function-redefined
                 shipping_method=None, billing_address=None, total=None, site=None, product_class=None, **kwargs):
    """
    Helper function for creating an order for testing
    """
    if not basket:
        basket = create_basket(owner=user, site=site, product_class=product_class)
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
                    enterprise_customer=None, site=None):
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
    condition = ConditionFactory(value=1, range=_range, enterprise_customer_uuid=enterprise_customer)
    if max_usage:
        offer = ConditionalOfferFactory(
            offer_type=ConditionalOffer.VOUCHER,
            benefit=benefit,
            condition=condition,
            max_global_applications=max_usage,
            email_domains=email_domains,
            priority=OFFER_PRIORITY_VOUCHER
        )
    else:
        offer = ConditionalOfferFactory(
            offer_type=ConditionalOffer.VOUCHER,
            benefit=benefit,
            condition=condition,
            email_domains=email_domains,
            partner=site.siteconfiguration.partner if site else None,
            priority=OFFER_PRIORITY_VOUCHER
        )
    voucher.offers.add(offer)
    return voucher, product


def prepare_enterprise_voucher(code='COUPONTEST', start_datetime=None, end_datetime=None, benefit_value=100,
                               benefit_type=Benefit.PERCENTAGE, usage=Voucher.SINGLE_USE,
                               enterprise_customer=None, enterprise_customer_catalog=None):
    """ Helper function to create a voucher and add an enterprise conditional offer to it. """
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
    benefit = BenefitFactory(
        proxy_class=class_path(ENTERPRISE_BENEFIT_MAP[benefit_type]),
        value=benefit_value,
        type='',
        range=None,
    )
    condition = ConditionFactory(
        proxy_class=class_path(EnterpriseCustomerCondition),
        enterprise_customer_uuid=enterprise_customer,
        enterprise_customer_catalog_uuid=enterprise_customer_catalog,
        range=None,
    )
    offer = ConditionalOfferFactory(
        offer_type=ConditionalOffer.VOUCHER,
        benefit=benefit,
        condition=condition,
        priority=OFFER_PRIORITY_VOUCHER
    )

    voucher.offers.add(offer)
    return voucher


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


class EnterpriseAbsoluteDiscountBenefitFactory(BenefitFactory):
    range = None
    type = ''
    value = 10
    proxy_class = class_path(EnterpriseAbsoluteDiscountBenefit)


class EnterprisePercentageDiscountBenefitFactory(BenefitFactory):
    range = None
    type = ''
    value = 10
    proxy_class = class_path(EnterprisePercentageDiscountBenefit)


class EnterpriseCustomerConditionFactory(ConditionFactory):
    range = None
    type = ''
    value = None
    enterprise_customer_uuid = factory.LazyFunction(uuid.uuid4)
    enterprise_customer_name = factory.Faker('word')
    enterprise_customer_catalog_uuid = factory.LazyFunction(uuid.uuid4)
    proxy_class = class_path(EnterpriseCustomerCondition)

    class Meta(object):
        model = EnterpriseCustomerCondition


class EnterpriseOfferFactory(ConditionalOfferFactory):
    benefit = factory.SubFactory(EnterprisePercentageDiscountBenefitFactory)
    condition = factory.SubFactory(EnterpriseCustomerConditionFactory)
    max_basket_applications = 1
    offer_type = ConditionalOffer.SITE
    priority = OFFER_PRIORITY_ENTERPRISE
    status = ConditionalOffer.OPEN


# TODO: journals dependency
class JournalAbsoluteDiscountBenefitFactory(BenefitFactory):
    range = None
    type = ''
    value = 10
    proxy_class = class_path(JournalBundleAbsoluteDiscountBenefit)


# TODO: journals dependency
class JournalPercentageDiscountBenefitFactory(BenefitFactory):
    range = None
    type = ''
    value = 10
    proxy_class = class_path(JournalBundlePercentageDiscountBenefit)


# TODO: journals dependency
class JournalConditionFactory(ConditionFactory):
    range = None
    type = ''
    value = None
    journal_bundle_uuid = factory.LazyFunction(uuid.uuid4)
    proxy_class = class_path(JournalBundleCondition)

    class Meta(object):
        model = JournalBundleCondition


# TODO: journals dependency
class JournalBundleOfferFactory(ConditionalOfferFactory):
    benefit = factory.SubFactory(JournalPercentageDiscountBenefitFactory)
    condition = factory.SubFactory(JournalConditionFactory)
    max_basket_applications = 1
    offer_type = ConditionalOffer.SITE
    priority = OFFER_PRIORITY_ENTERPRISE
    status = ConditionalOffer.OPEN
