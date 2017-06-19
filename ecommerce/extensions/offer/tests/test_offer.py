import urllib
from decimal import Decimal

import httpretty
from django.core.urlresolvers import reverse
from oscar.core.loading import get_class, get_model
from oscar.test import factories
from oscar.test.basket import add_product
from oscar.test.factories import RangeFactory

from ecommerce.enterprise.tests.mixins import EnterpriseServiceMockMixin
from ecommerce.extensions.partner.strategy import DefaultStrategy
from ecommerce.extensions.test.factories import (
    EnterpriseCustomerUserAbsoluteDiscountBenefitFactory, EnterpriseCustomerUserPercentageBenefitFactory,
    ProductFactory
)
from ecommerce.tests.mixins import EnterpriseMixin
from ecommerce.tests.testcases import TransactionTestCase

ConditionalOffer = get_model('offer', 'ConditionalOffer')
Condition = get_model('offer', 'Condition')
Benefit = get_model('offer', 'Benefit')
Applicator = get_class('offer.utils', 'Applicator')


class EnterpriseOfferTests(EnterpriseMixin, EnterpriseServiceMockMixin, TransactionTestCase):
    """
    Base class containing helper functions for enterprise benefit tests.
    """
    def setUp(self):
        """
        Common setup operations for each test case.
        """
        super(EnterpriseOfferTests, self).setUp()

        self.range = RangeFactory(includes_all_products=True)
        self.user = self.create_user(is_staff=True)
        self.client.login(username=self.user.username, password=self.password)

    def _create_enterprise_percent_benefit(self):
        """
        Create Enterprise benefit for percentage discounts on product prices.
        """
        benefit = EnterpriseCustomerUserPercentageBenefitFactory(range=self.range)
        condition = factories.ConditionFactory(
            range=self.range, proxy_class='ecommerce.extensions.offer.models.DataSharingConsentCondition'
        )

        return benefit, condition

    def _create_enterprise_absolute_benefit(self):
        """
        Create Enterprise benefit for absolute discounts on product prices.
        """
        benefit = EnterpriseCustomerUserAbsoluteDiscountBenefitFactory(range=self.range)
        condition = factories.ConditionFactory(
            range=self.range, proxy_class='ecommerce.extensions.offer.models.DataSharingConsentCondition'
        )

        return benefit, condition

    def _create_conditional_offer(self, benefit, condition):
        """
        Create conditional offer using given benefit and condition.
        """
        products = ProductFactory.create_batch(3, stockrecords__partner=self.partner)
        factories.ConditionalOfferFactory(
            benefit=benefit, condition=condition, offer_type=ConditionalOffer.SITE,
        )

        return products

    def _mock_api(self, enterprise_customer_uuid, consent_enabled, consent_provided):
        """
        Mock enterprise service api with given enterprise info.
        """
        self.mock_access_token_response()
        self.mock_enterprise_learner_api(
            learner_id=self.user.id,
            enterprise_customer_uuid=enterprise_customer_uuid,
            consent_enabled=consent_enabled,
            consent_provided=consent_provided,
        )


@httpretty.activate
class EnterpriseOfferBasketViewTests(EnterpriseOfferTests):
    """
    Tests for enterprise entitlement discount with data sharing consent conditions applied.
    """

    @staticmethod
    def _get_basket_url(products):
        """
        Get URL for the basket with sku of the given products
        """
        qs = urllib.urlencode({'sku': [product.stockrecords.first().partner_sku for product in products]}, True)
        path = reverse('api:v2:baskets:calculate')

        return '{root}?{qs}'.format(root=path, qs=qs)

    def test_enterprise_percent_entitlement_on_basket_when_consent_disabled(self):
        """
        Verify that enterprise entitlements are applied when
            1. Enterprise Customer has disabled consent

        If an enterprise customer has disabled consent then learner should get discounts
        on all of the enterprise sponsored courses irrespective of his/her data sharing consent
        state.
        """
        benefit, condition = self._create_enterprise_percent_benefit()
        self._mock_api(
            str(benefit.enterprise_customer_uuid),
            consent_enabled=False,
            consent_provided=False,
        )
        products = self._create_conditional_offer(benefit, condition)
        response = self.client.get(self._get_basket_url(products))

        product_total = sum(product.stockrecords.first().price_excl_tax for product in products)
        expected = {
            'total_incl_tax_excl_discounts': product_total,
            'total_incl_tax': Decimal('27.00'),  # 10% Discount on 3, 9.99 pound courses is 3 pounds
            'currency': 'GBP'
        }

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, expected)

    def test_enterprise_percent_entitlement_on_basket_when_consent_enabled_and_provided(self):
        """
        Verify that enterprise entitlements are applied when
            1. Enterprise Customer has required learner's consent to share data.
            2. Enterprise learner has consented to data sharing

        If an enterprise customer has required learner's consent to share data then learner
        must consent to data sharing before getting any discounts on enterprise sponsored courses.
        """
        benefit, condition = self._create_enterprise_percent_benefit()
        self._mock_api(
            str(benefit.enterprise_customer_uuid),
            consent_enabled=True,
            consent_provided=True,
        )
        products = self._create_conditional_offer(benefit, condition)
        response = self.client.get(self._get_basket_url(products))

        product_total = sum(product.stockrecords.first().price_excl_tax for product in products)
        expected = {
            'total_incl_tax_excl_discounts': product_total,
            'total_incl_tax': Decimal('27.00'),  # 10% Discount on 3, 9.99 pound courses is 3 pounds
            'currency': 'GBP'
        }

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, expected)

    def test_enterprise_percent_entitlement_on_basket_when_consent_enabled_but_not_provided(self):
        """
        Verify that enterprise entitlements are not applied when
            1. Enterprise Customer has required learner's consent to share data.
            2. Enterprise learner has not consented to data sharing

        If an enterprise customer has required learner's consent to share data then learner
        must consent to data sharing before getting any discounts on enterprise sponsored courses.
        """
        benefit, condition = self._create_enterprise_percent_benefit()
        self._mock_api(
            str(benefit.enterprise_customer_uuid),
            consent_enabled=True,
            consent_provided=False,
        )
        products = self._create_conditional_offer(benefit, condition)
        response = self.client.get(self._get_basket_url(products))

        product_total = sum(product.stockrecords.first().price_excl_tax for product in products)
        expected = {
            'total_incl_tax_excl_discounts': product_total,
            'total_incl_tax': Decimal('29.97'),  # Total price of 3, 9.99 pound courses is 29.97 pounds
            'currency': 'GBP'
        }

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, expected)

    def test_enterprise_absolute_entitlement_on_basket_when_consent_disabled(self):
        """
        Verify that enterprise entitlements are applied when
            1. Enterprise Customer has disabled consent

        If an enterprise customer has disabled consent then learner should get discounts
        on all of the enterprise sponsored courses irrespective of his/her data sharing consent
        state.
        """
        benefit, condition = self._create_enterprise_absolute_benefit()
        self._mock_api(
            str(benefit.enterprise_customer_uuid),
            consent_enabled=False,
            consent_provided=False,
        )
        self.mock_access_token_response()
        products = self._create_conditional_offer(benefit, condition)
        response = self.client.get(self._get_basket_url(products))

        product_total = sum(product.stockrecords.first().price_excl_tax for product in products)
        expected = {
            'total_incl_tax_excl_discounts': product_total,
            'total_incl_tax': Decimal('19.97'),  # absolute discount of 10 pound is applied
            'currency': 'GBP'
        }

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, expected)

    def test_enterprise_absolute_entitlement_on_basket_when_consent_enabled_and_provided(self):
        """
        Verify that enterprise entitlements are applied when
            1. Enterprise Customer has required learner's consent to share data.
            2. Enterprise learner has consented to data sharing

        If an enterprise customer has required learner's consent to share data then learner
        must consent to data sharing before getting any discounts on enterprise sponsored courses.
        """
        benefit, condition = self._create_enterprise_absolute_benefit()
        self._mock_api(
            str(benefit.enterprise_customer_uuid),
            consent_enabled=True,
            consent_provided=True,
        )
        products = self._create_conditional_offer(benefit, condition)
        response = self.client.get(self._get_basket_url(products))

        product_total = sum(product.stockrecords.first().price_excl_tax for product in products)
        expected = {
            'total_incl_tax_excl_discounts': product_total,
            'total_incl_tax': Decimal('19.97'),  # absolute discount of 10 pound is applied
            'currency': 'GBP'
        }

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, expected)

    def test_enterprise_absolute_entitlement_on_basket_when_consent_enabled_but_not_provided(self):
        """
        Verify that enterprise entitlements are not applied when
            1. Enterprise Customer has required learner's consent to share data.
            2. Enterprise learner has not consented to data sharing

        If an enterprise customer has required learner's consent to share data then learner
        must consent to data sharing before getting any discounts on enterprise sponsored courses.
        """
        benefit, condition = self._create_enterprise_absolute_benefit()
        self._mock_api(
            str(benefit.enterprise_customer_uuid),
            consent_enabled=True,
            consent_provided=False,
        )
        products = self._create_conditional_offer(benefit, condition)
        response = self.client.get(self._get_basket_url(products))

        product_total = sum(product.stockrecords.first().price_excl_tax for product in products)
        expected = {
            'total_incl_tax_excl_discounts': product_total,
            'total_incl_tax': Decimal('29.97'),  # Total price of 3, 9.99 pound courses is 29.97
            'currency': 'GBP'
        }

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, expected)


@httpretty.activate
class EnterpriseOfferBasketDiscountTests(EnterpriseOfferTests):
    """
    Tests for enterprise entitlement discount with data sharing consent conditions applied.
    """

    def test_enterprise_percent_entitlement_on_basket_when_consent_disabled(self):
        """
        Verify that enterprise entitlements are applied when
            1. Enterprise Customer has disabled consent

        If an enterprise customer has disabled consent then learner should get discounts
        on all of the enterprise sponsored courses irrespective of his/her data sharing consent
        state.
        """
        benefit, condition = self._create_enterprise_percent_benefit()
        self._mock_api(
            str(benefit.enterprise_customer_uuid),
            consent_enabled=False,
            consent_provided=True,
        )
        self._create_conditional_offer(benefit, condition)
        basket = factories.BasketFactory(site=self.site, owner=self.create_user())
        add_product(basket, Decimal('12.00'), 2)

        # No discounts should be applied, and each line should have a price of 24.00.
        self.assertEqual(len(basket.offer_applications), 0)
        self.assertEqual(basket.total_discount, 0)
        for line in basket.all_lines():
            self.assertEqual(line.line_price_incl_tax_incl_discounts, Decimal('24.00'))

        # Apply the offers as Oscar will in a request
        basket.strategy = DefaultStrategy()
        Applicator().apply(basket, basket.owner)

        # Our discount should be applied, and each line should have adjusted price of 21.60
        lines = basket.all_lines()
        self.assertEqual(len(basket.offer_applications), 1)
        self.assertEqual(basket.total_discount, Decimal('2.40') * len(lines))  # 10% discount on 24.00 is 2.40
        for line in lines:
            self.assertEqual(line.line_price_incl_tax_incl_discounts, Decimal('21.60'))

    def test_enterprise_percent_entitlement_on_basket_when_consent_enabled_and_provided(self):
        """
        Verify that enterprise entitlements are applied when
            1. Enterprise Customer has required learner's consent to share data.
            2. Enterprise learner has consented to data sharing

        If an enterprise customer has required learner's consent to share data then learner
        must consent to data sharing before getting any discounts on enterprise sponsored courses.
        """
        benefit, condition = self._create_enterprise_percent_benefit()
        self._mock_api(
            str(benefit.enterprise_customer_uuid),
            consent_enabled=True,
            consent_provided=True,
        )
        self._create_conditional_offer(benefit, condition)
        basket = factories.BasketFactory(site=self.site, owner=self.create_user())

        # Add one course run seat from each course to the basket.
        add_product(basket, Decimal('12.00'), 2)

        # No discounts should be applied, and each line should have a price of 24.00.
        self.assertEqual(len(basket.offer_applications), 0)
        self.assertEqual(basket.total_discount, 0)
        for line in basket.all_lines():
            self.assertEqual(line.line_price_incl_tax_incl_discounts, Decimal('24.00'))

        # Apply the offers as Oscar will in a request
        basket.strategy = DefaultStrategy()
        Applicator().apply(basket, basket.owner)

        # Our discount should be applied, and each line should have adjusted price of 21.60
        lines = basket.all_lines()
        self.assertEqual(len(basket.offer_applications), 1)
        self.assertEqual(basket.total_discount, Decimal('2.40') * len(lines))  # 10% discount on 24.00 is 2.40
        for line in lines:
            self.assertEqual(line.line_price_incl_tax_incl_discounts, Decimal('21.60'))

    def test_enterprise_percent_entitlement_on_basket_when_consent_enabled_but_not_provided(self):
        """
        Verify that enterprise entitlements are not applied when
            1. Enterprise Customer has required learner's consent to share data.
            2. Enterprise learner has not consented to data sharing

        If an enterprise customer has required learner's consent to share data then learner
        must consent to data sharing before getting any discounts on enterprise sponsored courses.
        """
        benefit, condition = self._create_enterprise_percent_benefit()
        self._mock_api(
            str(benefit.enterprise_customer_uuid),
            consent_enabled=True,
            consent_provided=False,
        )
        self._create_conditional_offer(benefit, condition)
        basket = factories.BasketFactory(site=self.site, owner=self.create_user())

        # Add one course run seat from each course to the basket.
        add_product(basket, Decimal('12.00'), 2)

        # No discounts should be applied, and each line should have a price of 24.00.
        self.assertEqual(len(basket.offer_applications), 0)
        self.assertEqual(basket.total_discount, 0)
        for line in basket.all_lines():
            self.assertEqual(line.line_price_incl_tax_incl_discounts, Decimal('24.00'))

        # Apply the offers as Oscar will in a request
        basket.strategy = DefaultStrategy()
        Applicator().apply(basket, basket.owner)

        # Since, learner did no consent to share data and enteprise customer requires the consent.
        # No discount should be applied, and each line should have a price of 24.00
        lines = basket.all_lines()
        self.assertEqual(len(basket.offer_applications), 0)
        self.assertEqual(basket.total_discount, Decimal('0.00') * len(lines))
        for line in lines:
            self.assertEqual(line.line_price_incl_tax_incl_discounts, Decimal('24.00'))

    def test_enterprise_absolute_entitlement_on_basket_when_consent_disabled(self):
        """
        Verify that enterprise entitlements are applied when
            1. Enterprise Customer has disabled consent

        If an enterprise customer has disabled consent then learner should get discounts
        on all of the enterprise sponsored courses irrespective of his/her data sharing consent
        state.
        """
        benefit, condition = self._create_enterprise_absolute_benefit()
        self._mock_api(
            str(benefit.enterprise_customer_uuid),
            consent_enabled=False,
            consent_provided=False,
        )
        self._create_conditional_offer(benefit, condition)
        basket = factories.BasketFactory(site=self.site, owner=self.create_user())

        # Add one course run seat from each course to the basket.
        add_product(basket, Decimal('12.00'), 2)

        # No discounts should be applied, and each line should have a price of 24.00.
        self.assertEqual(len(basket.offer_applications), 0)
        self.assertEqual(basket.total_discount, 0)
        for line in basket.all_lines():
            self.assertEqual(line.line_price_incl_tax_incl_discounts, Decimal('24.00'))

        # Apply the offers as Oscar will in a request
        basket.strategy = DefaultStrategy()
        Applicator().apply(basket, basket.owner)

        # Our discount should be applied, and each line should have adjusted price of 14.00
        lines = basket.all_lines()
        self.assertEqual(len(basket.offer_applications), 1)
        # absolute discount of 10 pound is applied
        self.assertEqual(basket.total_discount, Decimal('10.00') * len(lines))
        for line in lines:
            self.assertEqual(line.line_price_incl_tax_incl_discounts, Decimal('14.00'))

    def test_enterprise_absolute_entitlement_on_basket_when_consent_enabled_and_provided(self):
        """
        Verify that enterprise entitlements are applied when
            1. Enterprise Customer has required learner's consent to share data.
            2. Enterprise learner has consented to data sharing

        If an enterprise customer has required learner's consent to share data then learner
        must consent to data sharing before getting any discounts on enterprise sponsored courses.
        """
        benefit, condition = self._create_enterprise_absolute_benefit()
        self._mock_api(
            str(benefit.enterprise_customer_uuid),
            consent_enabled=True,
            consent_provided=True,
        )
        self._create_conditional_offer(benefit, condition)
        basket = factories.BasketFactory(site=self.site, owner=self.create_user())

        # Add one course run seat from each course to the basket.
        add_product(basket, Decimal('12.00'), 2)

        # No discounts should be applied, and each line should have a price of 24.00.
        self.assertEqual(len(basket.offer_applications), 0)
        self.assertEqual(basket.total_discount, 0)
        for line in basket.all_lines():
            self.assertEqual(line.line_price_incl_tax_incl_discounts, Decimal('24.00'))

        # Apply the offers as Oscar will in a request
        basket.strategy = DefaultStrategy()
        Applicator().apply(basket, basket.owner)

        # Our discount should be applied, and each line should have adjusted price of 14.00
        lines = basket.all_lines()
        self.assertEqual(len(basket.offer_applications), 1)
        # absolute discount of 10 pound is applied
        self.assertEqual(basket.total_discount, Decimal('10.00') * len(lines))
        for line in lines:
            self.assertEqual(line.line_price_incl_tax_incl_discounts, Decimal('14.00'))

    def test_enterprise_absolute_entitlement_on_basket_when_consent_enabled_but_not_provided(self):
        """
        Verify that enterprise entitlements are not applied when
            1. Enterprise Customer has required learner's consent to share data.
            2. Enterprise learner has not consented to data sharing

        If an enterprise customer has required learner's consent to share data then learner
        must consent to data sharing before getting any discounts on enterprise sponsored courses.
        """
        benefit, condition = self._create_enterprise_absolute_benefit()
        self._mock_api(
            str(benefit.enterprise_customer_uuid),
            consent_enabled=True,
            consent_provided=False,
        )
        self._create_conditional_offer(benefit, condition)
        basket = factories.BasketFactory(site=self.site, owner=self.create_user())

        # Add one course run seat from each course to the basket.
        add_product(basket, Decimal('12.00'), 2)

        # No discounts should be applied, and each line should have a price of 24.00.
        self.assertEqual(len(basket.offer_applications), 0)
        self.assertEqual(basket.total_discount, 0)
        for line in basket.all_lines():
            self.assertEqual(line.line_price_incl_tax_incl_discounts, Decimal('24.00'))

        # Apply the offers as Oscar will in a request
        basket.strategy = DefaultStrategy()
        Applicator().apply(basket, basket.owner)

        # Since, learner did no consent to share data and enteprise customer requires the consent.
        # No discount should be applied, and each line should have a price of 24.00
        lines = basket.all_lines()
        self.assertEqual(len(basket.offer_applications), 0)
        self.assertEqual(basket.total_discount, Decimal('0.00') * len(lines))
        for line in lines:
            self.assertEqual(line.line_price_incl_tax_incl_discounts, Decimal('24.00'))
