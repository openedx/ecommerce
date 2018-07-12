from decimal import Decimal
from uuid import uuid4

import ddt
import httpretty
from oscar.core.loading import get_model
from waffle.models import Switch

from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.enterprise.constants import ENTERPRISE_OFFERS_SWITCH
from ecommerce.enterprise.tests.mixins import EnterpriseServiceMockMixin
from ecommerce.extensions.basket.utils import basket_add_enterprise_catalog_attribute
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.extensions.test import factories
from ecommerce.tests.factories import ProductFactory, SiteConfigurationFactory
from ecommerce.tests.testcases import TestCase

Product = get_model('catalogue', 'Product')
LOGGER_NAME = 'ecommerce.programs.conditions'


@ddt.ddt
class EnterpriseCustomerConditionTests(EnterpriseServiceMockMixin, DiscoveryTestMixin, TestCase):
    def setUp(self):
        super(EnterpriseCustomerConditionTests, self).setUp()
        Switch.objects.update_or_create(name=ENTERPRISE_OFFERS_SWITCH, defaults={'active': True})
        self.user = factories.UserFactory()
        self.condition = factories.EnterpriseCustomerConditionFactory()
        self.test_product = ProductFactory(stockrecords__price_excl_tax=10, categories=[])
        self.course_run = CourseFactory()
        self.course_run.create_or_update_seat('verified', True, Decimal(100), self.partner)

    def test_name(self):
        """ The name should contain the EnterpriseCustomer's name. """
        condition = factories.EnterpriseCustomerConditionFactory()
        expected = "Basket contains a seat from {}'s catalog".format(condition.enterprise_customer_name)
        self.assertEqual(condition.name, expected)

    @httpretty.activate
    def test_is_satisfied_true(self):
        """ Ensure the condition returns true if all basket requirements are met. """
        offer = factories.EnterpriseOfferFactory(site=self.site, condition=self.condition)
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
        offer = factories.EnterpriseOfferFactory(site=self.site, condition=self.condition)
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
        offer = factories.EnterpriseOfferFactory(site=self.site, condition=self.condition)
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
        offer = factories.EnterpriseOfferFactory(site=self.site, condition=self.condition)

        basket = factories.BasketFactory(site=self.site, owner=self.user)
        basket.strategy.request = self.request
        basket.strategy.request.GET = {'catalog': invalid_enterprise_catalog_uuid}
        self._check_condition_is_satisfied(offer, basket, is_satisfied=False)
        assert invalid_enterprise_catalog_uuid != offer.condition.enterprise_customer_catalog_uuid

    @httpretty.activate
    def test_is_satisfied_for_anonymous_user(self):
        """ Ensure the condition returns false for an anonymous user. """
        offer = factories.EnterpriseOfferFactory(site=self.site, condition=self.condition)
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

    def test_is_satisfied_empty_basket(self):
        """ Ensure the condition returns False if the basket is empty. """
        offer = factories.EnterpriseOfferFactory(site=self.site, condition=self.condition)
        basket = factories.BasketFactory(site=self.site, owner=self.user)
        self.assertTrue(basket.is_empty)
        self.assertFalse(self.condition.is_satisfied(offer, basket))

    def test_is_satisfied_free_basket(self):
        """ Ensure the condition returns False if the basket total is zero. """
        offer = factories.EnterpriseOfferFactory(site=self.site, condition=self.condition)
        basket = factories.BasketFactory(site=self.site, owner=self.user)
        test_product = factories.ProductFactory(
            stockrecords__price_excl_tax=0,
            stockrecords__partner__short_code='test'
        )
        basket.add_product(test_product)
        self.assertFalse(self.condition.is_satisfied(offer, basket))

    def test_is_satisfied_site_mismatch(self):
        """ Ensure the condition returns False if the offer site does not match the basket site. """
        offer = factories.EnterpriseOfferFactory(site=SiteConfigurationFactory().site, condition=self.condition)
        basket = factories.BasketFactory(site=self.site, owner=self.user)
        basket.add_product(self.test_product)
        self.assertFalse(self.condition.is_satisfied(offer, basket))

    @httpretty.activate
    def test_is_satisfied_enterprise_learner_error(self):
        """ Ensure the condition returns false if the enterprise learner data cannot be retrieved. """
        offer = factories.EnterpriseOfferFactory(site=self.site, condition=self.condition)
        basket = factories.BasketFactory(site=self.site, owner=self.user)
        basket.add_product(self.course_run.seat_products[0])
        self.mock_enterprise_learner_api_raise_exception()
        self.assertFalse(self.condition.is_satisfied(offer, basket))

    @httpretty.activate
    def test_is_satisfied_no_enterprise_learner(self):
        """ Ensure the condition returns false if the learner is not linked to an EnterpriseCustomer. """
        offer = factories.EnterpriseOfferFactory(site=self.site, condition=self.condition)
        basket = factories.BasketFactory(site=self.site, owner=self.user)
        basket.add_product(self.course_run.seat_products[0])
        self.mock_enterprise_learner_api_for_learner_with_no_enterprise()
        self.assertFalse(self.condition.is_satisfied(offer, basket))

    @httpretty.activate
    def test_is_satisfied_wrong_enterprise(self):
        """ Ensure the condition returns false if the learner is associated with a different EnterpriseCustomer. """
        offer = factories.EnterpriseOfferFactory(site=self.site, condition=self.condition)
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
        offer = factories.EnterpriseOfferFactory(site=self.site, condition=self.condition)
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
        offer = factories.EnterpriseOfferFactory(site=self.site, condition=self.condition)
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
