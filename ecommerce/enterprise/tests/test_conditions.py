import datetime
from decimal import Decimal
from uuid import uuid4

import ddt
import httpretty
import mock
from django.utils.timezone import now
from oscar.core.loading import get_model
from waffle.models import Switch

from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.enterprise.conditions import EnterpriseCustomerCondition
from ecommerce.enterprise.constants import ENTERPRISE_OFFERS_FOR_COUPONS_SWITCH, ENTERPRISE_OFFERS_SWITCH
from ecommerce.enterprise.tests.mixins import EnterpriseServiceMockMixin
from ecommerce.extensions.basket.utils import basket_add_enterprise_catalog_attribute
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.extensions.offer.constants import (
    OFFER_ASSIGNMENT_EMAIL_PENDING,
    OFFER_ASSIGNED,
    OFFER_ASSIGNMENT_REVOKED,
    OFFER_REDEEMED,
)
from ecommerce.extensions.test import factories
from ecommerce.tests.factories import ProductFactory, SiteConfigurationFactory
from ecommerce.tests.testcases import TestCase

ConditionalOffer = get_model('offer', 'ConditionalOffer')
Product = get_model('catalogue', 'Product')
Voucher = get_model('voucher', 'Voucher')
LOGGER_NAME = 'ecommerce.programs.conditions'


@ddt.ddt
class EnterpriseCustomerConditionTests(EnterpriseServiceMockMixin, DiscoveryTestMixin, TestCase):
    def setUp(self):
        super(EnterpriseCustomerConditionTests, self).setUp()
        Switch.objects.update_or_create(name=ENTERPRISE_OFFERS_SWITCH, defaults={'active': True})
        self.user = factories.UserFactory()
        self.condition = factories.EnterpriseCustomerConditionFactory()
        self.test_product = ProductFactory(stockrecords__price_excl_tax=10, categories=[])
        self.course_run = CourseFactory(partner=self.partner)
        self.course_run.create_or_update_seat('verified', True, Decimal(100))

    def test_name(self):
        """ The name should contain the EnterpriseCustomer's name. """
        condition = factories.EnterpriseCustomerConditionFactory()
        expected = "Basket contains a seat from {}'s catalog".format(condition.enterprise_customer_name)
        self.assertEqual(condition.name, expected)

    @httpretty.activate
    def test_is_satisfied_true(self):
        """ Ensure the condition returns true if all basket requirements are met. """
        offer = factories.EnterpriseOfferFactory(partner=self.partner, condition=self.condition)
        basket = factories.BasketFactory(site=self.site, owner=self.user)
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
        basket = factories.BasketFactory(site=self.site, owner=self.user)
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
        basket = factories.BasketFactory(site=self.site, owner=self.user)
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

        basket = factories.BasketFactory(site=self.site, owner=self.user)
        basket.strategy.request = self.request
        basket.strategy.request.GET = {'catalog': invalid_enterprise_catalog_uuid}
        self._check_condition_is_satisfied(offer, basket, is_satisfied=False)
        assert invalid_enterprise_catalog_uuid != offer.condition.enterprise_customer_catalog_uuid

    @httpretty.activate
    def test_is_satisfied_for_anonymous_user(self):
        """ Ensure the condition returns false for an anonymous user. """
        offer = factories.EnterpriseOfferFactory(partner=self.partner, condition=self.condition)
        basket = factories.BasketFactory(site=self.site, owner=None)
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

    def setup_enterprise_coupon_data(self, mock_learner_api=True):
        offer = factories.EnterpriseOfferFactory(
            partner=self.partner,
            condition=self.condition,
            offer_type=ConditionalOffer.VOUCHER
        )
        basket = factories.BasketFactory(site=self.site, owner=self.user)
        basket.add_product(self.course_run.seat_products[0])
        if mock_learner_api:
            self.mock_enterprise_learner_api(
                learner_id=self.user.id,
                enterprise_customer_uuid=str(self.condition.enterprise_customer_uuid),
                course_run_id=self.course_run.id,
            )
        else:
            self.mock_enterprise_learner_api_for_learner_with_no_enterprise()

        self.mock_catalog_contains_course_runs(
            [self.course_run.id],
            self.condition.enterprise_customer_uuid,
            enterprise_customer_catalog_uuid=self.condition.enterprise_customer_catalog_uuid,
        )
        return offer, basket

    @httpretty.activate
    def test_is_satisfied_false_for_voucher_offer_coupon_switch_off(self):
        """ Ensure the condition returns false for a coupon with an enterprise conditional offer. """
        Switch.objects.update_or_create(name=ENTERPRISE_OFFERS_FOR_COUPONS_SWITCH, defaults={'active': False})
        offer, basket = self.setup_enterprise_coupon_data()
        self.assertFalse(self.condition.is_satisfied(offer, basket))

    @httpretty.activate
    def test_is_satisfied_true_for_voucher_offer_coupon_switch_on(self):
        """ Ensure the condition returns true for a coupon with an enterprise conditional offer. """
        Switch.objects.update_or_create(name=ENTERPRISE_OFFERS_FOR_COUPONS_SWITCH, defaults={'active': True})
        offer, basket = self.setup_enterprise_coupon_data()
        self.assertTrue(self.condition.is_satisfied(offer, basket))

    @httpretty.activate
    def test_is_satisfied_true_for_voucher_offer_coupon_switch_on_new_user(self):
        """ Ensure the condition returns true for a coupon with an enterprise conditional offer. """
        Switch.objects.update_or_create(name=ENTERPRISE_OFFERS_FOR_COUPONS_SWITCH, defaults={'active': True})
        offer, basket = self.setup_enterprise_coupon_data(mock_learner_api=False)
        self.assertTrue(self.condition.is_satisfied(offer, basket))

    def test_is_satisfied_empty_basket(self):
        """ Ensure the condition returns False if the basket is empty. """
        offer = factories.EnterpriseOfferFactory(partner=self.partner, condition=self.condition)
        basket = factories.BasketFactory(site=self.site, owner=self.user)
        self.assertTrue(basket.is_empty)
        self.assertFalse(self.condition.is_satisfied(offer, basket))

    def test_is_satisfied_free_basket(self):
        """ Ensure the condition returns False if the basket total is zero. """
        offer = factories.EnterpriseOfferFactory(partner=self.partner, condition=self.condition)
        basket = factories.BasketFactory(site=self.site, owner=self.user)
        test_product = factories.ProductFactory(
            stockrecords__price_excl_tax=0,
            stockrecords__partner__short_code='test'
        )
        basket.add_product(test_product)
        self.assertFalse(self.condition.is_satisfied(offer, basket))

    def test_is_satisfied_site_mismatch(self):
        """ Ensure the condition returns False if the offer partner does not match the basket site partner. """
        offer = factories.EnterpriseOfferFactory(partner=SiteConfigurationFactory().partner, condition=self.condition)
        basket = factories.BasketFactory(site=self.site, owner=self.user)
        basket.add_product(self.test_product)
        self.assertFalse(self.condition.is_satisfied(offer, basket))

    @httpretty.activate
    def test_is_satisfied_enterprise_learner_error(self):
        """ Ensure the condition returns false if the enterprise learner data cannot be retrieved. """
        offer = factories.EnterpriseOfferFactory(partner=self.partner, condition=self.condition)
        basket = factories.BasketFactory(site=self.site, owner=self.user)
        basket.add_product(self.course_run.seat_products[0])
        self.mock_enterprise_learner_api_raise_exception()
        self.assertFalse(self.condition.is_satisfied(offer, basket))

    @httpretty.activate
    def test_is_satisfied_no_enterprise_learner(self):
        """ Ensure the condition returns false if the learner is not linked to an EnterpriseCustomer. """
        offer = factories.EnterpriseOfferFactory(partner=self.partner, condition=self.condition)
        basket = factories.BasketFactory(site=self.site, owner=self.user)
        basket.add_product(self.course_run.seat_products[0])
        self.mock_enterprise_learner_api_for_learner_with_no_enterprise()
        self.assertFalse(self.condition.is_satisfied(offer, basket))

    @httpretty.activate
    def test_is_satisfied_wrong_enterprise(self):
        """ Ensure the condition returns false if the learner is associated with a different EnterpriseCustomer. """
        offer = factories.EnterpriseOfferFactory(partner=self.partner, condition=self.condition)
        basket = factories.BasketFactory(site=self.site, owner=self.user)
        basket.add_product(self.course_run.seat_products[0])
        self.mock_enterprise_learner_api(
            learner_id=self.user.id,
            course_run_id=self.course_run.id,
        )
        self.assertFalse(self.condition.is_satisfied(offer, basket))

    @httpretty.activate
    def test_is_satisfied_no_course_product(self):
        """ Ensure the condition returns false if the basket contains a product not associated with a course run. """
        offer = factories.EnterpriseOfferFactory(partner=self.partner, condition=self.condition)
        basket = factories.BasketFactory(site=self.site, owner=self.user)
        basket.add_product(self.test_product)
        self.mock_enterprise_learner_api(
            learner_id=self.user.id,
            enterprise_customer_uuid=str(self.condition.enterprise_customer_uuid),
            course_run_id=self.course_run.id,
        )
        self.assertFalse(self.condition.is_satisfied(offer, basket))

    @httpretty.activate
    def test_is_satisfied_course_run_not_in_catalog(self):
        """ Ensure the condition returns false if the course run is not in the Enterprise catalog. """
        offer = factories.EnterpriseOfferFactory(partner=self.partner, condition=self.condition)
        basket = factories.BasketFactory(site=self.site, owner=self.user)
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


@ddt.ddt
class AssignableEnterpriseCustomerCondition(EnterpriseServiceMockMixin, DiscoveryTestMixin, TestCase):
    def setUp(self):
        super(AssignableEnterpriseCustomerCondition, self).setUp()
        self.condition = factories.AssignableEnterpriseCustomerConditionFactory()

    def create_data(self, voucher_type, max_uses, assignments):
        """
        Create vouchers, offers and offer assignments.
        """
        if voucher_type == Voucher.SINGLE_USE:
            enterprise_offer = factories.EnterpriseOfferFactory()

        for assignment in assignments:
            code = assignment['code']

            if voucher_type != Voucher.SINGLE_USE:
                enterprise_offer = factories.EnterpriseOfferFactory(max_global_applications=max_uses)

            voucher, __ = Voucher.objects.get_or_create(
                usage=voucher_type,
                code=code,
                defaults={
                    'start_datetime': now() - datetime.timedelta(days=10),
                    'end_datetime': now() + datetime.timedelta(days=10),
                }
            )
            voucher.offers.add(enterprise_offer)

            factories.OfferAssignmentFactory(offer=enterprise_offer, code=code, user_email=assignment['user_email'])

    def assert_condition(self, voucher_type, assignments, expected_condition_result):
        """
        Verify that condition works as expected for different vouchers and assignments.
        """
        for assignment in assignments:
            code = assignment['code']
            email = assignment['user_email']

            voucher = Voucher.objects.get(usage=voucher_type, code=code)
            basket = factories.BasketFactory(site=self.site, owner=factories.UserFactory(email=email))
            basket.vouchers.add(voucher)

            is_condition_satisfied = self.condition.is_satisfied(voucher.enterprise_offer, basket)
            assert is_condition_satisfied == expected_condition_result

            # update the `num_orders` so that we can also verify the redemptions check
            if expected_condition_result:
                voucher.num_orders += 1
                voucher.save()

    @mock.patch.object(EnterpriseCustomerCondition, 'is_satisfied', mock.Mock(return_value=True))
    @ddt.data(
        (0, 'test1@example.com', OFFER_ASSIGNMENT_EMAIL_PENDING, True),
        (1, 'test1@example.com', OFFER_REDEEMED, False),
        (0, 'test1@example.com', OFFER_ASSIGNMENT_REVOKED, False),
    )
    @ddt.unpack
    def test_is_satisfied(self, num_orders, email, offer_status, condition_result):
        """
        Ensure that condition returns expected result.
        """
        voucher = factories.VoucherFactory(usage=Voucher.SINGLE_USE, num_orders=num_orders)
        enterprise_offer = factories.EnterpriseOfferFactory(max_global_applications=None)
        voucher.offers.add(enterprise_offer)
        basket = factories.BasketFactory(site=self.site, owner=factories.UserFactory(email=email))
        basket.vouchers.add(voucher)
        factories.OfferAssignmentFactory(
            offer=enterprise_offer,
            code=voucher.code,
            user_email=email,
            status=offer_status,
        )

        is_condition_satisfied = self.condition.is_satisfied(enterprise_offer, basket)
        self.assertEqual(is_condition_satisfied, condition_result)

    @mock.patch.object(EnterpriseCustomerCondition, 'is_satisfied', mock.Mock(return_value=True))
    def test_is_satisfied_with_different_users(self):
        """
        Ensure that condition returns expected result when wrong user is try to redeem the voucher.

        # code = 'ASD' assigned_to = 'test1@example.com'
        # code = 'ZXC' assigned_to = 'test2@example.com'
        # test2@example.com try to redeem `ASD` code
        # `is_satisfied` should return False
        """
        voucher1 = factories.VoucherFactory(usage=Voucher.SINGLE_USE, code='ASD')
        voucher2 = factories.VoucherFactory(usage=Voucher.SINGLE_USE, code='ZXC')

        enterprise_offers = factories.EnterpriseOfferFactory.create_batch(2)
        voucher1.offers.add(enterprise_offers[0])
        voucher2.offers.add(enterprise_offers[1])

        basket = factories.BasketFactory(site=self.site, owner=factories.UserFactory(email='test2@example.com'))
        basket.vouchers.add(voucher1)

        factories.OfferAssignmentFactory(offer=enterprise_offers[0], code=voucher1.code, user_email='test1@example.com')
        factories.OfferAssignmentFactory(offer=enterprise_offers[1], code=voucher2.code, user_email='test2@example.com')

        is_condition_satisfied = self.condition.is_satisfied(enterprise_offers[1], basket)
        self.assertFalse(is_condition_satisfied)

    @mock.patch.object(EnterpriseCustomerCondition, 'is_satisfied', mock.Mock(return_value=True))
    @ddt.data(
        (
            Voucher.SINGLE_USE,
            None,
            [
                {'code': 'ZZZCYOBK4BSGKGKF', 'user_email': 'test1@example.com'},
                {'code': 'KUGOW7Z37KUTGRI6', 'user_email': 'test2@example.com'},
            ],
            [
                {'code': 'ZZZCYOBK4BSGKGKF', 'user_email': 'test1@example.com'},
                {'code': 'ZZZCYOBK4BSGKGKF', 'user_email': 'test2@example.com'},
                {'code': 'KUGOW7Z37KUTGRI6', 'user_email': 'test1@example.com'},
            ]
        ),
        (
            Voucher.ONCE_PER_CUSTOMER,
            2,
            [
                {'code': 'KM2CDM3M3V3AY62Q', 'user_email': 'test1@example.com'},
                {'code': 'KM2CDM3M3V3AY62Q', 'user_email': 'test2@example.com'},
            ],
            [
                {'code': 'KM2CDM3M3V3AY62Q', 'user_email': 'none@example.com'}
            ]
        ),
        (
            Voucher.MULTI_USE,
            None,
            [
                {'code': 'TA7WCQD3T4C7GHZ4', 'user_email': 'test1@example.com'},
                {'code': 'TA7WCQD3T4C7GHZ4', 'user_email': 'test2@example.com'},
            ],
            [
                {'code': 'TA7WCQD3T4C7GHZ4', 'user_email': 'bob@example.com'}
            ]
        ),
        (
            Voucher.MULTI_USE,
            3,
            [
                {'code': 'NWW3BEOKOY5GITFH', 'user_email': 't1@example.com'},
                {'code': 'NWW3BEOKOY5GITFH', 'user_email': 't2@example.com'},
                {'code': 'NWW3BEOKOY5GITFH', 'user_email': 't3@example.com'},
                {'code': 'GLPDHRB7JJYY2MEK', 'user_email': 't4@example.com'},
            ],
            [
                {'code': 'NWW3BEOKOY5GITFH', 'user_email': 't4@example.com'},
                {'code': 'GLPDHRB7JJYY2MEK', 'user_email': 't3@example.com'},
            ]
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
            ]
        )
    )
    @ddt.unpack
    def test_is_satisfied_for_all_voucher_types(self, voucher_type, max_uses, assignments, wrong_assignments):
        """
        Ensure that condition returns expected result for `Voucher.MULTI_USE` voucher assignments.
        """
        self.create_data(voucher_type, max_uses, assignments)

        self.assert_condition(voucher_type, assignments, True)
        self.assert_condition(voucher_type, wrong_assignments, False)
