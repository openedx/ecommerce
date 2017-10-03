import uuid

import httpretty
from django.core.urlresolvers import reverse
from oscar.core.loading import get_model

from ecommerce.enterprise.benefits import EnterprisePercentageDiscountBenefit
from ecommerce.enterprise.tests.mixins import EnterpriseServiceMockMixin
from ecommerce.extensions.test import factories
from ecommerce.programs.custom import class_path
from ecommerce.tests.testcases import TestCase, ViewTestMixin

Benefit = get_model('offer', 'Benefit')
ConditionalOffer = get_model('offer', 'ConditionalOffer')


class EnterpriseOfferListViewTests(EnterpriseServiceMockMixin, ViewTestMixin, TestCase):

    path = reverse('enterprise:offers:list')

    def setUp(self):
        super(EnterpriseOfferListViewTests, self).setUp()

        httpretty.enable()
        self.mock_access_token_response()

    def tearDown(self):
        super(EnterpriseOfferListViewTests, self).tearDown()
        httpretty.disable()
        httpretty.reset()

    def test_get(self):
        """ The context should contain a list of enterprise offers. """

        # These should be ignored since their associated Condition objects do NOT have an Enterprise Customer UUID.
        factories.ConditionalOfferFactory.create_batch(3)

        enterprise_offers = factories.EnterpriseOfferFactory.create_batch(4, site=self.site)

        for offer in enterprise_offers:
            self.mock_specific_enterprise_customer_api(offer.condition.enterprise_customer_uuid)

        response = self.assert_get_response_status(200)
        self.assertEqual(list(response.context['object_list']), enterprise_offers)

        # The page should load even if the Enterprise API is inaccessible
        httpretty.disable()
        response = self.assert_get_response_status(200)
        self.assertEqual(list(response.context['object_list']), enterprise_offers)

    def test_get_queryset(self):
        """ Should return only Conditional Offers with Site offer type. """

        # Conditional Offer should contain a condition with enterprise customer uuid set in order to be returned
        site_conditional_offer = factories.EnterpriseOfferFactory(site=self.site)

        # Conditional Offer with null Site or non-matching Site should not be returned
        null_site_offer = factories.EnterpriseOfferFactory()
        different_site_offer = factories.EnterpriseOfferFactory(site=factories.SiteConfigurationFactory().site)
        enterprise_offers = [
            site_conditional_offer,
            factories.EnterpriseOfferFactory(offer_type=ConditionalOffer.VOUCHER),
            factories.ConditionalOfferFactory(offer_type=ConditionalOffer.SITE),
            null_site_offer,
            different_site_offer
        ]

        for offer in enterprise_offers:
            self.mock_specific_enterprise_customer_api(offer.condition.enterprise_customer_uuid)

        response = self.client.get(self.path)
        self.assertEqual(list(response.context['object_list']), [site_conditional_offer])


class EnterpriseOfferUpdateViewTests(EnterpriseServiceMockMixin, ViewTestMixin, TestCase):

    def setUp(self):
        super(EnterpriseOfferUpdateViewTests, self).setUp()
        self.enterprise_offer = factories.EnterpriseOfferFactory(site=self.site)
        self.path = reverse('enterprise:offers:edit', kwargs={'pk': self.enterprise_offer.pk})

        # NOTE: We activate httpretty here so that we don't have to decorate every test method.
        httpretty.enable()
        self.mock_specific_enterprise_customer_api(self.enterprise_offer.condition.enterprise_customer_uuid)

    def tearDown(self):
        super(EnterpriseOfferUpdateViewTests, self).tearDown()
        httpretty.disable()
        httpretty.reset()

    def test_get(self):
        """ The context should contain the enterprise offer. """
        response = self.assert_get_response_status(200)
        self.assertEqual(response.context['object'], self.enterprise_offer)

        # The page should load even if the Enterprise API is inaccessible
        httpretty.disable()
        response = self.assert_get_response_status(200)
        self.assertEqual(response.context['object'], self.enterprise_offer)

    def test_post(self):
        """ The enterprise offer should be updated. """
        data = {
            'enterprise_customer_uuid': self.enterprise_offer.condition.enterprise_customer_uuid,
            'enterprise_customer_catalog_uuid': self.enterprise_offer.condition.enterprise_customer_catalog_uuid,
            'benefit_type': self.enterprise_offer.benefit.proxy().benefit_class_type,
            'benefit_value': self.enterprise_offer.benefit.value,
        }
        response = self.client.post(self.path, data, follow=False)
        self.assertRedirects(response, self.path)


@httpretty.activate
class EnterpriseOfferCreateViewTests(EnterpriseServiceMockMixin, ViewTestMixin, TestCase):

    path = reverse('enterprise:offers:new')

    def test_post(self):
        """ A new enterprise offer should be created. """
        expected_ec_uuid = uuid.uuid4()
        expected_ec_catalog_uuid = uuid.uuid4()
        self.mock_specific_enterprise_customer_api(expected_ec_uuid)
        expected_benefit_value = 10
        data = {
            'enterprise_customer_uuid': expected_ec_uuid,
            'enterprise_customer_catalog_uuid': expected_ec_catalog_uuid,
            'benefit_type': Benefit.PERCENTAGE,
            'benefit_value': expected_benefit_value,
        }
        response = self.client.post(self.path, data, follow=False)
        enterprise_offer = ConditionalOffer.objects.get()

        self.assertRedirects(response, reverse('enterprise:offers:edit', kwargs={'pk': enterprise_offer.pk}))
        self.assertIsNone(enterprise_offer.start_datetime)
        self.assertIsNone(enterprise_offer.end_datetime)
        self.assertEqual(enterprise_offer.condition.enterprise_customer_uuid, expected_ec_uuid)
        self.assertEqual(enterprise_offer.condition.enterprise_customer_catalog_uuid, expected_ec_catalog_uuid)
        self.assertEqual(enterprise_offer.benefit.type, '')
        self.assertEqual(enterprise_offer.benefit.value, expected_benefit_value)
        self.assertEqual(enterprise_offer.benefit.proxy_class, class_path(EnterprisePercentageDiscountBenefit))
