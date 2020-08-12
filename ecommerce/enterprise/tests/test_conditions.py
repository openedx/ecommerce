

import unittest
from decimal import Decimal
from uuid import uuid4

import ddt
import httpretty
import mock
from oscar.core.loading import get_model
from oscar.test.factories import BasketFactory, OrderDiscountFactory, OrderFactory
from requests.exceptions import ConnectionError as ReqConnectionError

from ecommerce.coupons.tests.mixins import CouponMixin, DiscoveryMockMixin
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.enterprise.conditions import EnterpriseCustomerCondition
from ecommerce.enterprise.tests.mixins import EnterpriseServiceMockMixin
from ecommerce.entitlements.utils import create_or_update_course_entitlement
from ecommerce.extensions.api.serializers import CouponCodeAssignmentSerializer
from ecommerce.extensions.basket.utils import basket_add_enterprise_catalog_attribute
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.extensions.fulfillment.status import ORDER
from ecommerce.extensions.offer.constants import (
    OFFER_ASSIGNMENT_EMAIL_PENDING,
    OFFER_ASSIGNMENT_REVOKED,
    OFFER_REDEEMED
)
from ecommerce.extensions.test import factories
from ecommerce.tests.factories import ProductFactory, SiteConfigurationFactory, UserFactory
from ecommerce.tests.testcases import TestCase

Benefit = get_model('offer', 'Benefit')
ConditionalOffer = get_model('offer', 'ConditionalOffer')
OfferAssignment = get_model('offer', 'OfferAssignment')
Product = get_model('catalogue', 'Product')
Voucher = get_model('voucher', 'Voucher')
StockRecord = get_model('partner', 'StockRecord')
Catalog = get_model('catalogue', 'Catalog')

LOGGER_NAME = 'ecommerce.programs.conditions'


@ddt.ddt
class EnterpriseCustomerConditionTests(EnterpriseServiceMockMixin, DiscoveryTestMixin, DiscoveryMockMixin, TestCase):
    def setUp(self):
        super(EnterpriseCustomerConditionTests, self).setUp()
        self.user = UserFactory()
        self.condition = factories.EnterpriseCustomerConditionFactory()

        self.test_product = ProductFactory(stockrecords__price_excl_tax=10, categories=[])
        self.course_run = CourseFactory(partner=self.partner)
        self.course_run.create_or_update_seat('verified', True, Decimal(100))

        self.entitlement = create_or_update_course_entitlement(
            'verified', 100, self.partner, 'edX-DemoX', 'edX Demo Entitlement'
        )
        self.entitlement_stock_record = StockRecord.objects.filter(product=self.entitlement).first()
        self.entitlement_catalog = Catalog.objects.create(partner=self.partner)
        self.entitlement_catalog.stock_records.add(self.entitlement_stock_record)

    def test_name(self):
        """ The name should contain the EnterpriseCustomer's name. """
        condition = factories.EnterpriseCustomerConditionFactory()
        expected = "Basket contains a seat from {}'s catalog".format(condition.enterprise_customer_name)
        self.assertEqual(condition.name, expected)

    @httpretty.activate
    def test_is_satisfied_true(self):
        """ Ensure the condition returns true if all basket requirements are met. """
        offer = factories.EnterpriseOfferFactory(partner=self.partner, condition=self.condition)
        basket = BasketFactory(site=self.site, owner=self.user)
        basket.add_product(self.course_run.seat_products[0])
        self.mock_enterprise_learner_api(
            learner_id=self.user.id,
            enterprise_customer_uuid=str(self.condition.enterprise_customer_uuid),
            course_run_id=self.course_run.id,
        )
        self.mock_catalog_contains_course_runs(
            [self.course_run.id],
            self.condition.enterprise_customer_uuid,
            enterprise_customer_catalog_uuid=self.condition.enterprise_customer_catalog_uuid,
        )
        self.assertTrue(self.condition.is_satisfied(offer, basket))

    def _check_condition_is_satisfied(self, offer, basket, is_satisfied):
        """
        Helper method to verify that conditional offer is valid for provided basket.
        """
        basket.add_product(self.course_run.seat_products[0])
        self.mock_enterprise_learner_api(
            learner_id=self.user.id,
            enterprise_customer_uuid=str(self.condition.enterprise_customer_uuid),
            course_run_id=self.course_run.id,
        )
        self.mock_catalog_contains_course_runs(
            [self.course_run.id],
            self.condition.enterprise_customer_uuid,
            enterprise_customer_catalog_uuid=self.condition.enterprise_customer_catalog_uuid,
            contains_content=is_satisfied,
        )
        assert is_satisfied == self.condition.is_satisfied(offer, basket)

    @httpretty.activate
    def test_is_satisfied_true_for_enterprise_catalog_in_get_request(self):
        """
        Ensure that condition returns true for valid enterprise catalog uuid in GET request.
        """
        offer = factories.EnterpriseOfferFactory(partner=self.partner, condition=self.condition)
        enterprise_catalog_uuid = str(self.condition.enterprise_customer_catalog_uuid)
        basket = BasketFactory(site=self.site, owner=self.user)
        basket.strategy.request = self.request
        basket.strategy.request.GET = {'catalog': enterprise_catalog_uuid}
        self._check_condition_is_satisfied(offer, basket, is_satisfied=True)

    @httpretty.activate
    def test_is_satisfied_true_for_enterprise_catalog_in_basket_attribute(self):
        """
        Ensure that condition returns true for valid enterprise catalog uuid in basket attribute.
        """
        offer = factories.EnterpriseOfferFactory(partner=self.partner, condition=self.condition)
        enterprise_catalog_uuid = str(self.condition.enterprise_customer_catalog_uuid)
        basket = BasketFactory(site=self.site, owner=self.user)
        request_data = {'catalog': enterprise_catalog_uuid}
        basket_add_enterprise_catalog_attribute(basket, request_data)
        self._check_condition_is_satisfied(offer, basket, is_satisfied=True)

    @httpretty.activate
    @ddt.data(str(uuid4()), 'INVALID_UUID_STRING')
    def test_is_satisfied_false_for_invalid_enterprise_catalog(self, invalid_enterprise_catalog_uuid):
        """
        Ensure the condition returns false if provided enterprise catalog UUID is invalid.
        """
        offer = factories.EnterpriseOfferFactory(partner=self.partner, condition=self.condition)

        basket = BasketFactory(site=self.site, owner=self.user)
        basket.strategy.request = self.request
        basket.strategy.request.GET = {'catalog': invalid_enterprise_catalog_uuid}
        self._check_condition_is_satisfied(offer, basket, is_satisfied=False)
        assert invalid_enterprise_catalog_uuid != offer.condition.enterprise_customer_catalog_uuid

    @httpretty.activate
    def test_is_satisfied_for_anonymous_user(self):
        """ Ensure the condition returns false for an anonymous user. """
        offer = factories.EnterpriseOfferFactory(partner=self.partner, condition=self.condition)
        basket = BasketFactory(site=self.site, owner=None)
        basket.add_product(self.course_run.seat_products[0])
        self.mock_enterprise_learner_api(
            learner_id=self.user.id,
            enterprise_customer_uuid=str(self.condition.enterprise_customer_uuid),
            course_run_id=self.course_run.id,
        )
        self.mock_catalog_contains_course_runs(
            [self.course_run.id],
            self.condition.enterprise_customer_uuid,
            enterprise_customer_catalog_uuid=self.condition.enterprise_customer_catalog_uuid,
        )
        self.assertFalse(self.condition.is_satisfied(offer, basket))

    def setup_enterprise_coupon_data(self, mock_learner_api=True, use_new_enterprise=False):
        offer = factories.EnterpriseOfferFactory(
            partner=self.partner,
            condition=self.condition,
            offer_type=ConditionalOffer.VOUCHER
        )
        basket = BasketFactory(site=self.site, owner=self.user)
        basket.add_product(self.course_run.seat_products[0])
        enterprise_id = self.condition.enterprise_customer_uuid
        if use_new_enterprise:
            enterprise_id = uuid4()
        if mock_learner_api:
            self.mock_enterprise_learner_api(
                learner_id=self.user.id,
                enterprise_customer_uuid=str(enterprise_id),
                course_run_id=self.course_run.id,
            )
        else:
            self.mock_enterprise_learner_api_for_learner_with_no_enterprise()

        self.mock_catalog_contains_course_runs(
            [self.course_run.id],
            enterprise_id,
            enterprise_customer_catalog_uuid=self.condition.enterprise_customer_catalog_uuid,
        )
        return offer, basket

    @httpretty.activate
    def test_is_satisfied_true_for_voucher_offer_coupon(self):
        """ Ensure the condition returns true for a coupon with an enterprise conditional offer. """
        offer, basket = self.setup_enterprise_coupon_data()
        self.assertTrue(self.condition.is_satisfied(offer, basket))

    @httpretty.activate
    def test_is_satisfied_false_for_voucher_offer_enterprise_mismatch(self):
        """ Ensure the condition returns false for a enterprise coupon where the user has a different enterprise. """
        self.mock_enterprise_learner_post_api()
        offer, basket = self.setup_enterprise_coupon_data(use_new_enterprise=True)
        self.assertFalse(self.condition.is_satisfied(offer, basket))

    @httpretty.activate
    def test_is_satisfied_true_for_voucher_offer_coupon_on_new_user(self):
        """ Ensure the condition returns true for a coupon with an enterprise conditional offer. """
        offer, basket = self.setup_enterprise_coupon_data(mock_learner_api=False)
        self.assertTrue(self.condition.is_satisfied(offer, basket))

    @httpretty.activate
    def test_is_satisfied_no_course_product_for_voucher_offer(self):
        """ Ensure the condition returns false if the basket contains a product not associated with a course run. """
        offer, basket = self.setup_enterprise_coupon_data()
        basket.flush()
        basket.add_product(self.test_product)
        self.assertFalse(self.condition.is_satisfied(offer, basket))

    def test_is_satisfied_empty_basket(self):
        """ Ensure the condition returns False if the basket is empty. """
        offer = factories.EnterpriseOfferFactory(partner=self.partner, condition=self.condition)
        basket = BasketFactory(site=self.site, owner=self.user)
        self.assertTrue(basket.is_empty)
        self.assertFalse(self.condition.is_satisfied(offer, basket))

    def test_is_satisfied_free_basket(self):
        """ Ensure the condition returns False if the basket total is zero. """
        offer = factories.EnterpriseOfferFactory(partner=self.partner, condition=self.condition)
        basket = BasketFactory(site=self.site, owner=self.user)
        test_product = factories.ProductFactory(
            stockrecords__price_excl_tax=0,
            stockrecords__partner__short_code='test'
        )
        basket.add_product(test_product)
        self.assertFalse(self.condition.is_satisfied(offer, basket))

    def test_is_satisfied_site_mismatch(self):
        """ Ensure the condition returns False if the offer partner does not match the basket site partner. """
        offer = factories.EnterpriseOfferFactory(partner=SiteConfigurationFactory().partner, condition=self.condition)
        basket = BasketFactory(site=self.site, owner=self.user)
        basket.add_product(self.test_product)
        self.assertFalse(self.condition.is_satisfied(offer, basket))

    @httpretty.activate
    def test_is_satisfied_enterprise_learner_error(self):
        """ Ensure the condition returns false if the enterprise learner data cannot be retrieved. """
        offer = factories.EnterpriseOfferFactory(partner=self.partner, condition=self.condition)
        basket = BasketFactory(site=self.site, owner=self.user)
        basket.add_product(self.course_run.seat_products[0])
        self.mock_enterprise_learner_api_raise_exception()
        self.assertFalse(self.condition.is_satisfied(offer, basket))

    @httpretty.activate
    def test_is_satisfied_no_enterprise_learner(self):
        """ Ensure the condition returns false if the learner is not linked to an EnterpriseCustomer. """
        offer = factories.EnterpriseOfferFactory(partner=self.partner, condition=self.condition)
        basket = BasketFactory(site=self.site, owner=self.user)
        basket.add_product(self.course_run.seat_products[0])
        self.mock_enterprise_learner_api_for_learner_with_no_enterprise()
        self.assertFalse(self.condition.is_satisfied(offer, basket))

    @httpretty.activate
    def test_is_satisfied_wrong_enterprise(self):
        """ Ensure the condition returns false if the learner is associated with a different EnterpriseCustomer. """
        offer = factories.EnterpriseOfferFactory(partner=self.partner, condition=self.condition)
        basket = BasketFactory(site=self.site, owner=self.user)
        basket.add_product(self.course_run.seat_products[0])
        self.mock_enterprise_learner_api(
            learner_id=self.user.id,
            course_run_id=self.course_run.id,
        )
        self.assertFalse(self.condition.is_satisfied(offer, basket))

    @httpretty.activate
    def test_is_satisfied_no_course_product(self):
        """
        Ensure the condition returns false if the basket contains a product
        not associated with a course run or course entitlement.
        """
        offer = factories.EnterpriseOfferFactory(partner=self.partner, condition=self.condition)
        basket = BasketFactory(site=self.site, owner=self.user)
        basket.add_product(self.test_product)
        self.mock_enterprise_learner_api(
            learner_id=self.user.id,
            enterprise_customer_uuid=str(self.condition.enterprise_customer_uuid),
            course_run_id=self.course_run.id,
        )
        self.assertFalse(self.condition.is_satisfied(offer, basket))

    @httpretty.activate
    def test_is_satisfied_with_course_entitlement(self):
        """ Ensure the condition returns true if the basket contains a course entitlement. """
        offer = factories.EnterpriseOfferFactory(partner=self.partner, condition=self.condition)
        basket = BasketFactory(site=self.site, owner=self.user)
        basket.add_product(self.entitlement)

        self.mock_course_detail_endpoint(
            discovery_api_url=self.site_configuration.discovery_api_url,
            course=self.entitlement
        )
        self.mock_enterprise_learner_api(
            learner_id=self.user.id,
            enterprise_customer_uuid=str(self.condition.enterprise_customer_uuid),
            course_run_id=self.course_run.id,
        )
        self.mock_catalog_contains_course_runs(
            [self.entitlement.attr.UUID],
            self.condition.enterprise_customer_uuid,
            enterprise_customer_catalog_uuid=self.condition.enterprise_customer_catalog_uuid,
        )

        self.assertTrue(self.condition.is_satisfied(offer, basket))

    @httpretty.activate
    def test_is_satisfied_with_course_entitlement_request_error(self):
        """ Ensure the condition returns False if an error occurs while fetching course details. """
        offer = factories.EnterpriseOfferFactory(partner=self.partner, condition=self.condition)
        basket = BasketFactory(site=self.site, owner=self.user)
        basket.add_product(self.entitlement)

        self.mock_course_detail_endpoint_error(
            self.entitlement,
            discovery_api_url=self.site_configuration.discovery_api_url,
            error=ReqConnectionError
        )
        self.mock_enterprise_learner_api(
            learner_id=self.user.id,
            enterprise_customer_uuid=str(self.condition.enterprise_customer_uuid),
            course_run_id=self.course_run.id,
        )
        self.mock_catalog_contains_course_runs(
            [self.entitlement.attr.UUID],
            self.condition.enterprise_customer_uuid,
            enterprise_customer_catalog_uuid=self.condition.enterprise_customer_catalog_uuid,
        )
        self.assertFalse(self.condition.is_satisfied(offer, basket))

    @httpretty.activate
    def test_is_satisfied_course_run_not_in_catalog(self):
        """ Ensure the condition returns false if the course run is not in the Enterprise catalog. """
        offer = factories.EnterpriseOfferFactory(partner=self.partner, condition=self.condition)
        basket = BasketFactory(site=self.site, owner=self.user)
        basket.add_product(self.course_run.seat_products[0])
        self.mock_enterprise_learner_api(
            learner_id=self.user.id,
            enterprise_customer_uuid=str(self.condition.enterprise_customer_uuid),
            course_run_id=self.course_run.id,
        )
        self.mock_catalog_contains_course_runs(
            [self.course_run.id],
            self.condition.enterprise_customer_uuid,
            enterprise_customer_catalog_uuid=self.condition.enterprise_customer_catalog_uuid,
            contains_content=False
        )
        self.assertFalse(self.condition.is_satisfied(offer, basket))

    @httpretty.activate
    def test_is_satisfied_contains_content_items_failure(self):
        """ Ensure the condition returns false if the contains_content_item call fails. """
        offer = factories.EnterpriseOfferFactory(partner=self.partner, condition=self.condition)
        basket = BasketFactory(site=self.site, owner=self.user)
        basket.add_product(self.course_run.seat_products[0])
        self.mock_enterprise_learner_api(
            learner_id=self.user.id,
            enterprise_customer_uuid=str(self.condition.enterprise_customer_uuid),
            course_run_id=self.course_run.id,
        )
        self.mock_catalog_contains_course_runs(
            [self.course_run.id],
            self.condition.enterprise_customer_uuid,
            enterprise_customer_catalog_uuid=self.condition.enterprise_customer_catalog_uuid,
            contains_content=False,
            raise_exception=True
        )
        self.assertFalse(self.condition.is_satisfied(offer, basket))

    @ddt.data(
        {
            'discount_type': Benefit.PERCENTAGE,
            'total_discount': Decimal(4800),
            'benefit_value': 100,
            'is_satisfied': True
        },
        {
            'discount_type': Benefit.PERCENTAGE,
            'total_discount': Decimal(4900),
            'benefit_value': 50,
            'is_satisfied': True
        },
        {
            'discount_type': Benefit.PERCENTAGE,
            'total_discount': Decimal(4910),
            'benefit_value': 50,
            'is_satisfied': False
        },
        {
            'discount_type': Benefit.FIXED,
            'total_discount': Decimal(4800),
            'benefit_value': 300,
            'is_satisfied': True
        },
        {
            'discount_type': Benefit.FIXED,
            'total_discount': Decimal(4810),
            'benefit_value': 300,
            'is_satisfied': False
        },
        {
            'discount_type': Benefit.FIXED,
            'total_discount': Decimal(4930),
            'benefit_value': 70,
            'is_satisfied': True
        },
        {
            'discount_type': Benefit.FIXED,
            'total_discount': Decimal(4980),
            'benefit_value': 70,
            'is_satisfied': False
        },
    )
    @ddt.unpack
    @httpretty.activate
    def test_offer_availability_with_max_discount(self, discount_type, total_discount, benefit_value, is_satisfied):
        """
        Verify that enterprise offer with discount type percentage and absolute, condition returns correct result
        based on total_discount(consumed discount so far) and discount on course price covered by the offer.
        """
        benefits = {
            Benefit.PERCENTAGE: factories.EnterprisePercentageDiscountBenefitFactory(value=benefit_value),
            Benefit.FIXED: factories.EnterpriseAbsoluteDiscountBenefitFactory(value=benefit_value),
        }

        offer = factories.EnterpriseOfferFactory(
            partner=self.partner,
            benefit=benefits[discount_type],
            max_discount=Decimal(5000),
            total_discount=total_discount
        )
        basket = BasketFactory(site=self.site, owner=self.user)
        basket.add_product(self.course_run.seat_products[0])
        basket.add_product(self.entitlement)
        self.mock_course_detail_endpoint(
            discovery_api_url=self.site_configuration.discovery_api_url,
            course=self.entitlement
        )
        self.mock_catalog_contains_course_runs(
            [self.course_run.id],
            self.condition.enterprise_customer_uuid,
            enterprise_customer_catalog_uuid=self.condition.enterprise_customer_catalog_uuid,
        )
        self.assertEqual(self.condition.is_satisfied(offer, basket), is_satisfied)

    @ddt.data(
        {
            'discount_type': Benefit.PERCENTAGE,
            'num_prev_orders': 6,
            'benefit_value': 50,
            'is_satisfied': False
        },
        {
            'discount_type': Benefit.PERCENTAGE,
            'num_prev_orders': 5,
            'benefit_value': 50,
            'is_satisfied': True
        },
        {
            'discount_type': Benefit.PERCENTAGE,
            'num_prev_orders': 0,
            'benefit_value': 50,
            'is_satisfied': True
        },
        {
            'discount_type': Benefit.FIXED,
            'num_prev_orders': 6,
            'benefit_value': 100,
            'is_satisfied': False
        },
        {
            'discount_type': Benefit.FIXED,
            'num_prev_orders': 5,
            'benefit_value': 300,
            'is_satisfied': False
        },
        {
            'discount_type': Benefit.FIXED,
            'num_prev_orders': 5,
            'benefit_value': 100,
            'is_satisfied': True
        },
        {
            'discount_type': Benefit.FIXED,
            'num_prev_orders': 0,
            'benefit_value': 150,
            'is_satisfied': True
        },
    )
    @ddt.unpack
    @httpretty.activate
    def test_offer_availability_with_max_user_discount(
            self, discount_type, num_prev_orders, benefit_value, is_satisfied):
        """
        Verify that enterprise offer with discount type percentage and absolute, condition returns correct result
        based on user limits in the offer.
        """
        benefits = {
            Benefit.PERCENTAGE: factories.EnterprisePercentageDiscountBenefitFactory(value=benefit_value),
            Benefit.FIXED: factories.EnterpriseAbsoluteDiscountBenefitFactory(value=benefit_value),
        }
        offer = factories.EnterpriseOfferFactory(
            partner=self.partner,
            benefit=benefits[discount_type],
            max_user_discount=150
        )
        for _ in range(num_prev_orders):
            order = OrderFactory(user=self.user, status=ORDER.COMPLETE)
            OrderDiscountFactory(order=order, offer_id=offer.id, amount=10)
        basket = BasketFactory(site=self.site, owner=self.user)
        basket.add_product(self.course_run.seat_products[0])
        basket.add_product(self.entitlement)
        self.mock_course_detail_endpoint(
            discovery_api_url=self.site_configuration.discovery_api_url,
            course=self.entitlement
        )
        self.mock_catalog_contains_course_runs(
            [self.course_run.id],
            self.condition.enterprise_customer_uuid,
            enterprise_customer_catalog_uuid=self.condition.enterprise_customer_catalog_uuid,
        )
        self.assertEqual(self.condition.is_satisfied(offer, basket), is_satisfied)

    @httpretty.activate
    def test_absolute_benefit_offer_availability_with_max_user_discount(self):
        """
        Verify that enterprise offer condition returns correct result for an absolute benefit with
        discount value greater than course price.
        """
        offer = factories.EnterpriseOfferFactory(
            partner=self.partner,
            benefit=factories.EnterpriseAbsoluteDiscountBenefitFactory(value=150),
            max_user_discount=150
        )
        for _ in range(5):
            order = OrderFactory(user=self.user, status=ORDER.COMPLETE)
            OrderDiscountFactory(order=order, offer_id=offer.id, amount=10)
        basket = BasketFactory(site=self.site, owner=self.user)
        basket.add_product(self.course_run.seat_products[0])
        self.mock_catalog_contains_course_runs(
            [self.course_run.id],
            self.condition.enterprise_customer_uuid,
            enterprise_customer_catalog_uuid=self.condition.enterprise_customer_catalog_uuid,
        )
        self.assertTrue(self.condition.is_satisfied(offer, basket))

    @httpretty.activate
    def test_absolute_benefit_offer_availability(self):
        """
        Verify that enterprise offer condition returns correct result for an absolute benefit with
        discount value greater than course price.
        """
        offer = factories.EnterpriseOfferFactory(
            partner=self.partner,
            benefit=factories.EnterpriseAbsoluteDiscountBenefitFactory(value=150),
            max_discount=Decimal(300),
            total_discount=Decimal(200)
        )
        basket = BasketFactory(site=self.site, owner=self.user)
        basket.add_product(self.course_run.seat_products[0])
        self.mock_catalog_contains_course_runs(
            [self.course_run.id],
            self.condition.enterprise_customer_uuid,
            enterprise_customer_catalog_uuid=self.condition.enterprise_customer_catalog_uuid,
        )
        self.assertTrue(self.condition.is_satisfied(offer, basket))


@ddt.ddt
class AssignableEnterpriseCustomerConditionTests(EnterpriseServiceMockMixin, CouponMixin, TestCase):
    def setUp(self):
        super(AssignableEnterpriseCustomerConditionTests, self).setUp()
        self.condition = factories.AssignableEnterpriseCustomerConditionFactory()

    def create_data(self, voucher_type, max_uses, assignments):
        """
        Create vouchers, offers and offer assignments.
        """
        codes = {assignment['code'] for assignment in assignments}
        emails = sorted({assignment['user_email'] for assignment in assignments})
        quantity = len(codes)

        voucher_types = (Voucher.MULTI_USE, Voucher.ONCE_PER_CUSTOMER, Voucher.MULTI_USE_PER_CUSTOMER)
        num_of_offers = quantity if voucher_type in voucher_types else 1

        offers = []
        for __ in range(num_of_offers):
            offers.append(factories.EnterpriseOfferFactory(max_global_applications=max_uses))

        coupon = self.create_coupon(quantity=quantity, voucher_type=voucher_type)
        for index, info in enumerate(zip(coupon.attr.coupon_vouchers.vouchers.all(), codes)):
            voucher, code = info
            voucher.code = code
            voucher.offers.add(offers[index] if len(offers) > 1 else offers[0])
            voucher.save()

        data = {'codes': codes, 'emails': emails}
        serializer = CouponCodeAssignmentSerializer(
            data=data,
            context={'coupon': coupon, 'template': 'An Email Template'}
        )
        if serializer.is_valid():
            serializer.save()
            assignments = serializer.data

    def assert_condition(self, voucher_type, assignments, expected_condition_result):
        """
        Verify that condition works as expected for different vouchers and assignments.
        """
        for assignment in assignments:
            code = assignment['code']
            email = assignment['user_email']
            # In some cases individual assignments have their own expected result
            expected_condition_result = assignment.get('result', expected_condition_result)

            voucher = Voucher.objects.get(usage=voucher_type, code=code)
            basket = BasketFactory(site=self.site, owner=UserFactory(email=email))
            basket.vouchers.add(voucher)

            is_condition_satisfied = self.condition.is_satisfied(voucher.enterprise_offer, basket)
            assert is_condition_satisfied == expected_condition_result

            # update the `num_orders` so that we can also verify the redemptions check
            # also update the offer assignment status
            if expected_condition_result:
                voucher.num_orders += 1
                voucher.save()
                assignment = OfferAssignment.objects.filter(
                    offer=voucher.enterprise_offer, code=code, user_email=email
                ).exclude(
                    status__in=[OFFER_REDEEMED, OFFER_ASSIGNMENT_REVOKED]
                ).first()
                if assignment:
                    assignment.status = OFFER_REDEEMED
                    assignment.save()

    @mock.patch('ecommerce.enterprise.conditions.crum.get_current_request')
    @mock.patch.object(EnterpriseCustomerCondition, 'is_satisfied', mock.Mock(return_value=True))
    @ddt.data(
        (0, 'test1@example.com', OFFER_ASSIGNMENT_EMAIL_PENDING, True),
        (1, 'test1@example.com', OFFER_REDEEMED, False),
        (0, 'test1@example.com', OFFER_ASSIGNMENT_REVOKED, True),
    )
    @ddt.unpack
    def test_is_satisfied(self, num_orders, email, offer_status, condition_result, mock_request):
        """
        Ensure that condition returns expected result.
        """
        mock_request.return_value = self.request
        voucher = factories.VoucherFactory(usage=Voucher.SINGLE_USE, num_orders=num_orders)
        enterprise_offer = factories.EnterpriseOfferFactory(max_global_applications=None)
        voucher.offers.add(enterprise_offer)
        basket = BasketFactory(site=self.site, owner=UserFactory(email=email))
        basket.vouchers.add(voucher)
        factories.OfferAssignmentFactory(
            offer=enterprise_offer,
            code=voucher.code,
            user_email=email,
            status=offer_status,
        )

        assert self.condition.is_satisfied(enterprise_offer, basket) == condition_result

    @mock.patch('ecommerce.enterprise.conditions.crum.get_current_request')
    @mock.patch.object(EnterpriseCustomerCondition, 'is_satisfied', mock.Mock(return_value=True))
    def test_is_satisfied_with_different_users(self, mock_request):
        """
        Ensure that condition returns expected result when wrong user is try to redeem the voucher.

        # code = 'ASD' assigned_to = 'test1@example.com'
        # code = 'ZXC' assigned_to = 'test2@example.com'
        # test2@example.com try to redeem `ASD` code
        # `is_satisfied` should return False
        """
        mock_request.return_value = self.request

        voucher1 = factories.VoucherFactory(usage=Voucher.SINGLE_USE, code='ASD')
        voucher2 = factories.VoucherFactory(usage=Voucher.SINGLE_USE, code='ZXC')

        enterprise_offers = factories.EnterpriseOfferFactory.create_batch(2)
        voucher1.offers.add(enterprise_offers[0])
        voucher2.offers.add(enterprise_offers[1])

        basket = BasketFactory(site=self.site, owner=UserFactory(email='test2@example.com'))
        basket.vouchers.add(voucher1)

        factories.OfferAssignmentFactory(offer=enterprise_offers[0], code=voucher1.code, user_email='test1@example.com')
        factories.OfferAssignmentFactory(offer=enterprise_offers[1], code=voucher2.code, user_email='test2@example.com')

        assert self.condition.is_satisfied(enterprise_offers[1], basket) is False

    @mock.patch('ecommerce.enterprise.conditions.crum.get_current_request')
    @mock.patch.object(EnterpriseCustomerCondition, 'is_satisfied', mock.Mock(return_value=True))
    @mock.patch('ecommerce.extensions.offer.utils.send_offer_assignment_email', mock.Mock())
    @ddt.data(
        (
            Voucher.SINGLE_USE,
            None,
            [
                {'code': 'ZZZCYOBK4BSGKGKF', 'user_email': 'test1@example.com'},
                {'code': 'KUGOW7Z37KUTGRI6', 'user_email': 'test2@example.com'},
            ],
            [
                {'code': 'KUGOW7Z37KUTGRI6', 'user_email': 'test1@example.com'},
                {'code': 'ZZZCYOBK4BSGKGKF', 'user_email': 'test1@example.com'},
                {'code': 'ZZZCYOBK4BSGKGKF', 'user_email': 'test2@example.com'},
            ],
            True
        ),
        (
            Voucher.SINGLE_USE,
            None,
            [
                {'code': 'ZZZCYOBK4BSGKGKF', 'user_email': 'test1@example.com'},
                {'code': 'KUGOW7Z37KUTGRI6', 'user_email': 'test2@example.com'},
            ],
            [
                {'code': 'KUGOW7Z37KUTGRI6', 'user_email': 'test1@example.com'},
                {'code': 'ZZZCYOBK4BSGKGKF', 'user_email': 'test2@example.com'},
            ],
            False
        ),
        (
            Voucher.ONCE_PER_CUSTOMER,
            2,
            [
                {'code': 'KM2CDM3M3V3AY62Q', 'user_email': 'test1@example.com'},
                {'code': 'KM2CDM3M3V3AY62Q', 'user_email': 'test2@example.com'},
            ],
            [
                {'code': 'KM2CDM3M3V3AY62Q', 'user_email': 'test1@example.com'},
                {'code': 'KM2CDM3M3V3AY62Q', 'user_email': 'other@example.com'},
            ],
            True
        ),
        (
            Voucher.ONCE_PER_CUSTOMER,
            5,
            [
                {'code': 'KM2CDM3M3V3AY62Q', 'user_email': 'test1@example.com'},
                {'code': 'KM2CDM3M3V3AY62Q', 'user_email': 'test2@example.com'},
            ],
            [
                # `other@example.com` should be able to redeem because we have slots available
                {'code': 'KM2CDM3M3V3AY62Q', 'user_email': 'other@example.com', 'result': True},
            ],
            True
        ),
        (
            Voucher.MULTI_USE,
            None,
            [
                {'code': 'TA7WCQD3T4C7GHZ4', 'user_email': 'test1@example.com'},
                {'code': 'TA7WCQD3T4C7GHZ4', 'user_email': 'test2@example.com'},
            ],
            [],
            True
        ),
        (
            Voucher.MULTI_USE,
            3,
            [
                {'code': 'NWW3BEOKOY5GITFH', 'user_email': 't1@example.com'},
                {'code': 'NWW3BEOKOY5GITFH', 'user_email': 't2@example.com'},
                {'code': 'NWW3BEOKOY5GITFH', 'user_email': 't3@example.com'},
            ],
            [
                {'code': 'NWW3BEOKOY5GITFH', 'user_email': 't4@example.com'},
            ],
            True
        ),
        (
            Voucher.MULTI_USE,
            5,
            [
                {'code': 'NWW3BEOKOY5GITFH', 'user_email': 't1@example.com'},
                {'code': 'NWW3BEOKOY5GITFH', 'user_email': 't2@example.com'},
                {'code': 'NWW3BEOKOY5GITFH', 'user_email': 't3@example.com'},
            ],
            [
                # `other@example.com` should be able to redeem because we have slots available
                {'code': 'NWW3BEOKOY5GITFH', 'user_email': 'other@example.com', 'result': True},
            ],
            True
        ),
        (
            Voucher.MULTI_USE_PER_CUSTOMER,
            3,
            [
                {'code': 'GAOJIXZLHMDJFMZE', 'user_email': 'test1@example.com'},
                {'code': 'GAOJIXZLHMDJFMZE', 'user_email': 'test1@example.com'},
                {'code': 'GAOJIXZLHMDJFMZE', 'user_email': 'test1@example.com'},
                {'code': '3ZVMFPE4WKMMKEUE', 'user_email': 'test2@example.com'},
                {'code': '3ZVMFPE4WKMMKEUE', 'user_email': 'test2@example.com'},
                {'code': '3ZVMFPE4WKMMKEUE', 'user_email': 'test2@example.com'},
            ],
            [
                {'code': 'GAOJIXZLHMDJFMZE', 'user_email': 'test1@example.com'},
                {'code': 'GAOJIXZLHMDJFMZE', 'user_email': 'test2@example.com'},
                {'code': '3ZVMFPE4WKMMKEUE', 'user_email': 'test1@example.com'},
                {'code': '3ZVMFPE4WKMMKEUE', 'user_email': 'other@example.com'},
            ],
            True
        ),
        (
            Voucher.MULTI_USE_PER_CUSTOMER,
            2,
            [
                {'code': 'PO73EDONFDRJIYL5', 'user_email': 'test1@example.com'},
                {'code': 'PO73EDONFDRJIYL5', 'user_email': 'test1@example.com'},
                {'code': 'LQUKUCDDVZZWM4VD', 'user_email': 'test2@example.com'},
                {'code': 'LQUKUCDDVZZWM4VD', 'user_email': 'test2@example.com'},
            ],
            [
                {'code': 'PO73EDONFDRJIYL5', 'user_email': 'test2@example.com'},
                {'code': 'LQUKUCDDVZZWM4VD', 'user_email': 'test1@example.com'},
            ],
            False
        )
    )
    @ddt.unpack
    # This test is being skipped because hash-randomization causes it to fail. The test needs to
    # assign coupons and emails more consistently.
    @unittest.skip("Skipped until INCR-575 is resolved")
    def test_is_satisfied_for_all_voucher_types(
            self,
            voucher_type,
            max_uses,
            assignments,
            wrong_assignments,
            check_correct_assignments,
            mock_request,
    ):
        """
        Ensure that condition returns expected result for all types of voucher assignments.
        """
        mock_request.return_value = self.request
        self.create_data(voucher_type, max_uses, assignments)

        # for correct assignments we will also update status in OfferAssignment Model
        # In some cases we only want to check the condition for wrong assignments
        # without redeeming the correct assignments
        if check_correct_assignments:
            self.assert_condition(voucher_type, assignments, True)
        self.assert_condition(voucher_type, wrong_assignments, False)

    @mock.patch('ecommerce.enterprise.conditions.crum.get_current_request')
    @mock.patch.object(EnterpriseCustomerCondition, 'is_satisfied', mock.Mock(return_value=True))
    def test_is_satisfied_when_owner_has_no_assignment(self, mock_request):
        """
        Ensure that condition returns expected result the basket owner has no assignments.

        # voucher has free slots(3) available, no offer assignment for basket owner,
        # assignments(2) exist for other users, voucher has some redemptions(num_orders = 2)
        # basket owner is allowed to redeem the voucher
        """
        mock_request.return_value = self.request
        code = 'TA7WCQD3T4C7GHZ4'
        num_orders = 2
        max_global_applications = 7

        enterprise_offer = factories.EnterpriseOfferFactory(max_global_applications=max_global_applications)
        voucher = factories.VoucherFactory(usage=Voucher.MULTI_USE, code=code, num_orders=num_orders)
        voucher.offers.add(enterprise_offer)

        factories.OfferAssignmentFactory(offer=enterprise_offer, code=code, user_email='test1@example.com')
        factories.OfferAssignmentFactory(offer=enterprise_offer, code=code, user_email='test2@example.com')

        basket = BasketFactory(site=self.site, owner=UserFactory(email='bob@example.com'))
        basket.vouchers.add(voucher)

        assert self.condition.is_satisfied(enterprise_offer, basket) is True

    @mock.patch('ecommerce.enterprise.conditions.crum.get_current_request')
    @mock.patch.object(EnterpriseCustomerCondition, 'is_satisfied', mock.Mock(return_value=True))
    def test_is_satisfied_when_user_has_no_assignment(self, mock_request):
        """
        Ensure that condition returns expected result when code has assignments
        but user has no assignments and free slots are available.
        """
        mock_request.return_value = self.request
        voucher_code = 'NWW3BEOKOY5GITFH'
        voucher_type, max_uses, assignments = (
            Voucher.MULTI_USE,
            7,
            [
                {'code': voucher_code, 'user_email': 't1@example.com'},
                {'code': voucher_code, 'user_email': 't2@example.com'},
            ]
        )
        user_with_no_assignment = [{'code': voucher_code, 'user_email': 'user_with_no_assignment@example.com'}]

        self.create_data(voucher_type, max_uses, assignments)

        # initially voucher should have 0 redemptions
        voucher = Voucher.objects.get(usage=voucher_type, code=voucher_code)
        assert voucher.num_orders == 0

        # after this voucher's num_orders should be 2
        self.assert_condition(voucher_type, assignments, True)
        voucher = Voucher.objects.get(usage=voucher_type, code=voucher_code)
        assert voucher.num_orders == 2

        # consume all free slots
        for __ in range(5):
            self.assert_condition(voucher_type, user_with_no_assignment, True)

        # all free slots should be redeemed
        voucher = Voucher.objects.get(usage=voucher_type, code=voucher_code)
        assert voucher.num_orders == 7

        # no redemption available
        self.assert_condition(voucher_type, user_with_no_assignment, False)

    @mock.patch('ecommerce.enterprise.conditions.crum.get_current_request')
    @mock.patch.object(EnterpriseCustomerCondition, 'is_satisfied', mock.Mock(return_value=True))
    @ddt.data(
        (0, True),
        (1, False),
    )
    @ddt.unpack
    def test_is_satisfied_when_no_code_assignments_exists(self, num_orders, redemptions_available, mock_request):
        """
        Ensure that condition returns expected result when code has no assignments.
        """
        mock_request.return_value = self.request
        enterprise_offer = factories.EnterpriseOfferFactory()
        voucher = factories.VoucherFactory(usage=Voucher.SINGLE_USE, code='AAA', num_orders=num_orders)
        voucher.offers.add(enterprise_offer)

        basket = BasketFactory(site=self.site, owner=UserFactory(email='wow@example.com'))
        basket.vouchers.add(voucher)

        assert self.condition.is_satisfied(enterprise_offer, basket) == redemptions_available
