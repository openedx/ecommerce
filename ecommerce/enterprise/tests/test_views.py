

import uuid

import responses
from django.conf import settings
from django.urls import reverse
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

        responses.start()
        self.mock_access_token_response()

    def tearDown(self):
        super(EnterpriseOfferListViewTests, self).tearDown()
        responses.stop()
        responses.reset()

    def test_get(self):
        """ The context should contain a list of enterprise offers. """

        # These should be ignored since their associated Condition objects do NOT have an Enterprise Customer UUID.
        factories.ConditionalOfferFactory.create_batch(3)

        enterprise_offers = factories.EnterpriseOfferFactory.create_batch(4, partner=self.partner)

        for offer in enterprise_offers:
            self.mock_specific_enterprise_customer_api(offer.condition.enterprise_customer_uuid)

        response = self.assert_get_response_status(200)
        self.assertEqual(list(response.context['object_list']), enterprise_offers)

        # The page should load even if the Enterprise API is inaccessible
        responses.reset()
        response = self.assert_get_response_status(200)
        self.assertEqual(list(response.context['object_list']), enterprise_offers)

    def test_get_queryset(self):
        """ Should return only Conditional Offers with Site offer type. """

        # Conditional Offer should contain a condition with enterprise customer uuid set in order to be returned
        partner_conditional_offer = factories.EnterpriseOfferFactory(partner=self.partner)

        # Conditional Offer with null Partner or non-matching Partner should not be returned
        null_partner_offer = factories.EnterpriseOfferFactory()
        different_partner_offer = factories.EnterpriseOfferFactory(partner=factories.SiteConfigurationFactory().partner)
        enterprise_offers = [
            partner_conditional_offer,
            factories.EnterpriseOfferFactory(offer_type=ConditionalOffer.VOUCHER),
            factories.ConditionalOfferFactory(offer_type=ConditionalOffer.SITE),
            null_partner_offer,
            different_partner_offer
        ]

        for offer in enterprise_offers:
            self.mock_specific_enterprise_customer_api(offer.condition.enterprise_customer_uuid)

        response = self.client.get(self.path)
        self.assertEqual(list(response.context['object_list']), [partner_conditional_offer])


class EnterpriseOfferUpdateViewTests(EnterpriseServiceMockMixin, ViewTestMixin, TestCase):

    def setUp(self):
        super(EnterpriseOfferUpdateViewTests, self).setUp()
        self.enterprise_offer = factories.EnterpriseOfferFactory(partner=self.partner)
        self.path = reverse('enterprise:offers:edit', kwargs={'pk': self.enterprise_offer.pk})
        responses.start()
        self.mock_specific_enterprise_customer_api(self.enterprise_offer.condition.enterprise_customer_uuid)

    def tearDown(self):
        super(EnterpriseOfferUpdateViewTests, self).tearDown()
        responses.reset()

    def test_get(self):
        """ The context should contain the enterprise offer. """
        response = self.assert_get_response_status(200)
        self.assertEqual(response.context['object'], self.enterprise_offer)

        # The page should load even if the Enterprise API is inaccessible
        responses.reset()
        response = self.assert_get_response_status(200)
        self.assertEqual(response.context['object'], self.enterprise_offer)

    def test_post(self):
        """ The enterprise offer should be updated. """
        data = {
            'enterprise_customer_uuid': self.enterprise_offer.condition.enterprise_customer_uuid,
            'enterprise_customer_catalog_uuid': self.enterprise_offer.condition.enterprise_customer_catalog_uuid,
            'benefit_type': self.enterprise_offer.benefit.proxy().benefit_class_type,
            'benefit_value': self.enterprise_offer.benefit.value,
            'contract_discount_type': 'Absolute',
            'contract_discount_value': 200,
            'prepaid_invoice_amount': 2000,
            'sales_force_id': '006abcde0123456789',
            'salesforce_opportunity_line_item': '000abcde9876543210',
            'usage_email_frequency': ConditionalOffer.DAILY
        }
        response = self.client.post(self.path, data, follow=False)
        self.assertRedirects(response, self.path)


class EnterpriseOfferCreateViewTests(EnterpriseServiceMockMixin, ViewTestMixin, TestCase):

    path = reverse('enterprise:offers:new')

    @responses.activate
    def test_post(self):
        """ A new enterprise offer should be created. """
        expected_ec_uuid = uuid.uuid4()
        expected_ec_catalog_uuid = uuid.uuid4()
        self.mock_specific_enterprise_customer_api(expected_ec_uuid)
        expected_benefit_value = 10
        expected_discount_value = 2000
        expected_discount_type = 'Absolute'
        expected_prepaid_invoice_amount = 12345
        sales_force_id = '006abcde0123456789'
        salesforce_opportunity_line_item = '000abcde9876543210'
        data = {
            'enterprise_customer_uuid': expected_ec_uuid,
            'enterprise_customer_catalog_uuid': expected_ec_catalog_uuid,
            'benefit_type': Benefit.PERCENTAGE,
            'benefit_value': expected_benefit_value,
            'contract_discount_value': expected_discount_value,
            'contract_discount_type': expected_discount_type,
            'prepaid_invoice_amount': expected_prepaid_invoice_amount,
            'sales_force_id': sales_force_id,
            'salesforce_opportunity_line_item': salesforce_opportunity_line_item,
            'usage_email_frequency': ConditionalOffer.DAILY
        }

        existing_offer_ids = list(ConditionalOffer.objects.all().values_list('id', flat=True))
        response = self.client.post(self.path, data, follow=False)
        conditional_offers = ConditionalOffer.objects.exclude(id__in=existing_offer_ids)
        enterprise_offer = conditional_offers.first()
        self.assertEqual(conditional_offers.count(), 1)
        self.assertRedirects(response, reverse('enterprise:offers:edit', kwargs={'pk': enterprise_offer.pk}))
        self.assertIsNone(enterprise_offer.start_datetime)
        self.assertIsNone(enterprise_offer.end_datetime)
        self.assertEqual(enterprise_offer.sales_force_id, sales_force_id)
        self.assertEqual(enterprise_offer.salesforce_opportunity_line_item, salesforce_opportunity_line_item)
        self.assertEqual(enterprise_offer.condition.enterprise_customer_uuid, expected_ec_uuid)
        self.assertEqual(enterprise_offer.condition.enterprise_customer_catalog_uuid, expected_ec_catalog_uuid)
        self.assertEqual(enterprise_offer.benefit.type, '')
        self.assertEqual(enterprise_offer.benefit.value, expected_benefit_value)
        self.assertEqual(enterprise_offer.benefit.proxy_class, class_path(EnterprisePercentageDiscountBenefit))
        self.assertEqual(
            enterprise_offer.enterprise_contract_metadata.discount_value,
            expected_discount_value
        )
        self.assertEqual(
            enterprise_offer.enterprise_contract_metadata.discount_type,
            expected_discount_type
        )
        self.assertEqual(
            enterprise_offer.enterprise_contract_metadata.amount_paid,
            expected_prepaid_invoice_amount
        )


class EnterpriseCouponAppViewTests(TestCase):
    path = reverse('enterprise:coupons', args=[''])

    def test_login_required(self):
        """ Users are required to login before accessing the view. """
        self.client.logout()
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 302)
        self.assertIn(settings.LOGIN_URL, response.url)

    def assert_response_status(self, is_staff, status_code):
        """Create a user and assert the status code from the response for that user."""
        user = self.create_user(is_staff=is_staff)
        self.client.login(username=user.username, password=self.password)
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, status_code)

    def test_staff_user_required(self):
        """ Verify the view is only accessible to staff users. """
        self.assert_response_status(is_staff=False, status_code=404)
        self.assert_response_status(is_staff=True, status_code=200)
