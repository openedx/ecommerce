

import logging
import uuid
from datetime import datetime, timedelta

import factory
from django.utils.timezone import now
from faker import Faker
from oscar.test.factories import Basket, BenefitFactory
from oscar.test.factories import ConditionalOfferFactory as BaseConditionalOfferFactory
from oscar.test.factories import (
    ConditionFactory,
    D,
    Free,
    OrderCreator,
    OrderTotalCalculator,
    ProductFactory,
    RangeFactory
)
from oscar.test.factories import VoucherFactory as BaseVoucherFactory
from oscar.test.factories import create_product, create_stockrecord, get_class, get_model

from ecommerce.enterprise.benefits import BENEFIT_MAP as ENTERPRISE_BENEFIT_MAP
from ecommerce.enterprise.benefits import EnterpriseAbsoluteDiscountBenefit, EnterprisePercentageDiscountBenefit
from ecommerce.enterprise.conditions import AssignableEnterpriseCustomerCondition, EnterpriseCustomerCondition
from ecommerce.extensions.offer.constants import DAY3, DAY10, DAY19
from ecommerce.extensions.offer.dynamic_conditional_offer import DynamicPercentageDiscountBenefit
from ecommerce.extensions.offer.models import (
    OFFER_PRIORITY_ENTERPRISE,
    OFFER_PRIORITY_MANUAL_ORDER,
    OFFER_PRIORITY_VOUCHER,
    CodeAssignmentNudgeEmails,
    CodeAssignmentNudgeEmailTemplates,
    OfferAssignment
)
from ecommerce.extensions.order.benefits import ManualEnrollmentOrderDiscountBenefit
from ecommerce.extensions.order.conditions import ManualEnrollmentOrderDiscountCondition
from ecommerce.extensions.payment.models import SDNFallbackData, SDNFallbackMetadata
from ecommerce.programs.benefits import AbsoluteDiscountBenefitWithoutRange, PercentageDiscountBenefitWithoutRange
from ecommerce.programs.conditions import ProgramCourseRunSeatsCondition
from ecommerce.programs.custom import class_path
from ecommerce.tests.factories import SiteConfigurationFactory, UserFactory

logger = logging.getLogger('faker')
logger.setLevel(logging.INFO)  # Quiet down faker locale messages in tests.

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
        start_datetime = now() - timedelta(days=1)

    if end_datetime is None:
        end_datetime = now() + timedelta(days=10)

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
        start_datetime = now() - timedelta(days=1)

    if end_datetime is None:
        end_datetime = now() + timedelta(days=10)

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

    class Meta:
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

    class Meta:
        model = EnterpriseCustomerCondition


class AssignableEnterpriseCustomerConditionFactory(ConditionFactory):
    proxy_class = class_path(AssignableEnterpriseCustomerCondition)

    class Meta:
        model = AssignableEnterpriseCustomerCondition


class ManualEnrollmentOrderDiscountConditionFactory(ConditionFactory):
    proxy_class = class_path(ManualEnrollmentOrderDiscountCondition)
    enterprise_customer_uuid = factory.LazyFunction(uuid.uuid4)

    class Meta:
        model = ManualEnrollmentOrderDiscountCondition


class ManualEnrollmentOrderDiscountBenefitFactory(BenefitFactory):
    range = None
    type = ''
    value = 100
    max_affected_items = 1
    proxy_class = class_path(ManualEnrollmentOrderDiscountBenefit)


class ManualEnrollmentOrderOfferFactory(ConditionalOfferFactory):
    benefit = factory.SubFactory(ManualEnrollmentOrderDiscountBenefitFactory)
    condition = factory.SubFactory(ManualEnrollmentOrderDiscountConditionFactory)
    max_basket_applications = None
    offer_type = ConditionalOffer.USER
    priority = OFFER_PRIORITY_MANUAL_ORDER
    status = ConditionalOffer.OPEN


class EnterpriseOfferFactory(ConditionalOfferFactory):
    benefit = factory.SubFactory(EnterprisePercentageDiscountBenefitFactory)
    condition = factory.SubFactory(EnterpriseCustomerConditionFactory)
    max_basket_applications = 1
    offer_type = ConditionalOffer.SITE
    priority = OFFER_PRIORITY_ENTERPRISE
    status = ConditionalOffer.OPEN
    emails_for_usage_alert = 'example_1@example.com, example_2@example.com'


class OfferAssignmentFactory(factory.DjangoModelFactory):
    offer = factory.SubFactory(EnterpriseOfferFactory)
    code = factory.Sequence(lambda n: 'VOUCHERCODE{number}'.format(number=n))
    user_email = factory.Sequence(lambda n: 'example_%s@example.com' % n)

    class Meta:
        model = OfferAssignment


class DynamicPercentageDiscountBenefitFactory(BenefitFactory):
    range = None
    type = ''
    value = 1
    proxy_class = class_path(DynamicPercentageDiscountBenefit)


class CodeAssignmentNudgeEmailTemplatesFactory(factory.DjangoModelFactory):
    email_greeting = factory.Faker('sentence')
    email_closing = factory.Faker('sentence')
    email_subject = factory.Faker('sentence')
    name = factory.Faker('name')
    email_type = factory.fuzzy.FuzzyChoice((DAY3, DAY10, DAY19))

    class Meta:
        model = CodeAssignmentNudgeEmailTemplates


class CodeAssignmentNudgeEmailsFactory(factory.DjangoModelFactory):
    email_template = factory.SubFactory(CodeAssignmentNudgeEmailTemplatesFactory)
    user_email = factory.Sequence(lambda n: 'learner_%s@example.com' % n)
    email_date = datetime.now()

    class Meta:
        model = CodeAssignmentNudgeEmails


class SDNFallbackMetadataFactory(factory.DjangoModelFactory):
    class Meta:
        model = SDNFallbackMetadata

    file_checksum = factory.Sequence(lambda n: Faker().md5())
    import_state = 'New'
    download_timestamp = datetime.now() - timedelta(days=10)


class SDNFallbackDataFactory(factory.DjangoModelFactory):
    class Meta:
        model = SDNFallbackData

    sdn_fallback_metadata = factory.SubFactory(SDNFallbackMetadataFactory)
    source = "Specially Designated Nationals (SDN) - Treasury Department"
    sdn_type = "Individual"
    names = factory.Faker('name')
    addresses = factory.Faker('address')
    countries = factory.Faker('country_code')
