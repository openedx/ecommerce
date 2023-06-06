import pytest
from django.core.management import call_command
from oscar.core.loading import get_model
from oscar.core.utils import slugify

from ecommerce.core.constants import (
    COUPON_PRODUCT_CLASS_NAME,
    COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME,
    ENROLLMENT_CODE_PRODUCT_CLASS_NAME,
    SEAT_PRODUCT_CLASS_NAME
)
from ecommerce.extensions.basket.constants import EMAIL_OPT_IN_ATTRIBUTE, PURCHASER_BEHALF_ATTRIBUTE
from ecommerce.extensions.catalogue.utils import create_subcategories
from ecommerce.extensions.checkout.signals import BUNDLE
from ecommerce.core.constants import ORDER_MANAGER_ROLE
from ecommerce.core.constants import DONATIONS_FROM_CHECKOUT_TESTS_PRODUCT_TYPE_NAME
from ecommerce.core.constants import ENTERPRISE_COUPON_ADMIN_ROLE


COUPON_CATEGORY_NAME = 'Coupons'

DEFAULT_CATEGORIES = [
    'Affiliate Promotion', 'Bulk Enrollment', 'ConnectEd', 'Course Promotion',
    'Customer Service', 'Financial Assistance', 'Geography Promotion',
    'Marketing Partner Promotion', 'Marketing-Other', 'Paid Cohort', 'Other',
    'Retention Promotion', 'Services-Other', 'Support-Other', 'Upsell Promotion',
    'Bulk Enrollment - Prepay',
    'Bulk Enrollment - Upon Redemption',
    'Bulk Enrollment - Integration',
    'On-Campus Learners',
    'Partner No Rev - Prepay',
    'Partner No Rev - Upon Redemption',
    'Security Disclosure Reward',
    'Partner No Rev - RAP',
    'Partner No Rev - ORAP',
    'B2B Affiliate Promotion',
    'Scholarship',
    'edX Employee Request',
]


@pytest.fixture(scope='session')
def django_db_setup(django_db_setup, django_db_blocker, django_db_use_migrations):
    if django_db_use_migrations:
        return

    with django_db_blocker.unblock():
        BasketAttributeType = get_model('basket', 'BasketAttributeType')
        Category = get_model("catalogue", "Category")
        ProductAttribute = get_model("catalogue", "ProductAttribute")
        ProductClass = get_model("catalogue", "ProductClass")
        Option = get_model("catalogue", "Option")
        EcommerceFeatureRole = get_model('core', 'EcommerceFeatureRole')
        Condition = get_model('offer', 'Condition')
        Benefit = get_model('offer', 'Benefit')
        ConditionalOffer = get_model('offer', 'ConditionalOffer')

        BasketAttributeType.objects.get_or_create(name=EMAIL_OPT_IN_ATTRIBUTE)
        BasketAttributeType.objects.get_or_create(name=PURCHASER_BEHALF_ATTRIBUTE)
        BasketAttributeType.objects.get_or_create(name=BUNDLE)

        for klass in (Category, ProductAttribute, ProductClass, Option):
            klass.skip_history_when_saving = True

        # Create a new product class for course seats
        seat, _ = ProductClass.objects.get_or_create(
            track_stock=False,
            requires_shipping=False,
            name=SEAT_PRODUCT_CLASS_NAME,
            slug=slugify(SEAT_PRODUCT_CLASS_NAME)
        )

        # Create product attributes for course seat products
        ProductAttribute.objects.get_or_create(
            product_class=seat,
            name="course_key",
            code="course_key",
            type="text",
            required=True
        )

        ProductAttribute.objects.get_or_create(
            product_class=seat,
            name="id_verification_required",
            code="id_verification_required",
            type="boolean",
            required=False
        )

        ProductAttribute.objects.get_or_create(
            product_class=seat,
            name="certificate_type",
            code="certificate_type",
            type="text",
            required=False
        )

        # Create a category for course seats
        Category.objects.get_or_create(
            description="All course seats",
            numchild=1,
            slug="seats",
            depth=1,
            path="0001",
            image="",
            name="Seats"
        )

        ProductAttribute.objects.get_or_create(
            product_class=seat,
            name='credit_provider',
            code='credit_provider',
            type='text',
            required=False
        )
        ProductAttribute.objects.get_or_create(
            product_class=seat,
            name='credit_hours',
            code='credit_hours',
            type='integer',
            required=False
        )

        Option.objects.get_or_create(
            name='Course Entitlement',
            code='course_entitlement',
            type=Option.OPTIONAL,
        )

        coupon, _ = ProductClass.objects.get_or_create(
            track_stock=False,
            requires_shipping=False,
            name=COUPON_PRODUCT_CLASS_NAME,
            slug=slugify(COUPON_PRODUCT_CLASS_NAME),
        )

        ProductAttribute.objects.get_or_create(
            product_class=coupon,
            name='Coupon vouchers',
            code='coupon_vouchers',
            type='entity',
            required=False
        )

        # Create a category for coupons.
        Category.objects.get_or_create(
            description='All Coupons',
            slug='coupons',
            depth=1,
            path='0002',
            image='',
            name='Coupons'
        )
        ProductAttribute.objects.create(
            product_class=coupon,
            name='Note',
            code='note',
            type='text',
            required=False
        )
        ProductAttribute.objects.create(
            product_class=coupon,
            name='Notification Email',
            code='notify_email',
            type='text',
            required=False
        )
        ProductAttribute.objects.create(
            product_class=coupon,
            name='Enterprise Customer UUID',
            code='enterprise_customer_uuid',
            type='text',
            required=False
        )
        ProductAttribute.objects.create(
            product_class=coupon,
            name='Enterprise Contract Metadata',
            code='enterprise_contract_metadata',
            type='entity',
            required=False
        )
        ProductAttribute.objects.create(
            product_class=coupon,
            name='Inactive',
            code='inactive',
            type=ProductAttribute.BOOLEAN,
            required=False
        )
        ProductAttribute.objects.create(
            product_class=coupon,
            name='Sales Force ID',
            code='sales_force_id',
            type='text',
            required=False
        )
        ProductAttribute.objects.create(
            product_class=coupon,
            name='Salesforce Opportunity Line Item',
            code='salesforce_opportunity_line_item',
            type='text',
            required=False
        )
        ProductAttribute.objects.create(
            product_class=coupon,
            name='Is Public Code?',
            code='is_public_code',
            type='boolean',
            required=False
        )

        # Create a new product class for course entitlement
        course_entitlement, _ = ProductClass.objects.get_or_create(
            track_stock=False,
            requires_shipping=False,
            name=COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME,
            slug=slugify(COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME)
        )

        # Create product attributes for course entitlement products
        ProductAttribute.objects.get_or_create(
            product_class=course_entitlement,
            name="UUID",
            code="UUID",
            type="text",
            required=True
        )

        ProductAttribute.objects.get_or_create(
            product_class=course_entitlement,
            name="certificate_type",
            code="certificate_type",
            type="text",
            required=False
        )

        ProductAttribute.objects.get_or_create(
            product_class=course_entitlement,
            name='id_verification_required',
            code='id_verification_required',
            type='boolean',
            required=False
        )

        try:
            Category.objects.get(name="Course Entitlements")
        except Category.DoesNotExist:
            # Create a category for course entitlements
            Category.add_root(
                description="All course entitlements",
                slug="course_entitlements",
                image="",
                name="Course Entitlements"
            )

        enrollment_code, _ = ProductClass.objects.get_or_create(
            track_stock=False,
            requires_shipping=False,
            name=ENROLLMENT_CODE_PRODUCT_CLASS_NAME,
            slug=slugify(ENROLLMENT_CODE_PRODUCT_CLASS_NAME),
        )

        ProductAttribute.objects.get_or_create(
            product_class=enrollment_code,
            name='Course Key',
            code='course_key',
            type='text',
            required=True
        )

        ProductAttribute.objects.get_or_create(
            product_class=enrollment_code,
            name='Seat Type',
            code='seat_type',
            type='text',
            required=True
        )

        ProductAttribute.objects.get_or_create(
            product_class=enrollment_code,
            name='id_verification_required',
            code='id_verification_required',
            type='boolean',
            required=False
        )

        EcommerceFeatureRole.objects.get_or_create(name=ORDER_MANAGER_ROLE)

        new_dynamic_condition, _ = Condition.objects.get_or_create(
            proxy_class='ecommerce.extensions.offer.dynamic_conditional_offer.DynamicDiscountCondition'
        )

        # The value doesn't matter, because it's dynamic, but oscar will complain without one.
        new_dynamic_benefit, _ = Benefit.objects.get_or_create(
            value=1,
            proxy_class='ecommerce.extensions.offer.dynamic_conditional_offer.DynamicPercentageDiscountBenefit'
        )

        ConditionalOffer.objects.get_or_create(
            name='dynamic_conditional_offer',
            benefit=new_dynamic_benefit,
            condition=new_dynamic_condition,
            max_basket_applications=1,
            priority=-10
        )

        # Create a new product class for donations for the donations from checkout tests
        ProductClass.objects.get_or_create(
            track_stock=False,
            requires_shipping=False,
            name=DONATIONS_FROM_CHECKOUT_TESTS_PRODUCT_TYPE_NAME,
            slug=slugify(DONATIONS_FROM_CHECKOUT_TESTS_PRODUCT_TYPE_NAME)
        )

        try:
            Category.objects.get(name="Donations")
        except Category.DoesNotExist:
            Category.add_root(
                description="All donations",
                slug="donations",
                image="",
                name="Donations"
            )

        EcommerceFeatureRole.objects.get_or_create(name=ENTERPRISE_COUPON_ADMIN_ROLE)

        create_subcategories(Category, COUPON_CATEGORY_NAME, DEFAULT_CATEGORIES)

