from urllib.parse import urlencode
from uuid import uuid4

import mock
from django.urls import reverse
from oscar.core.loading import get_model
from oscar.test.factories import OrderFactory, OrderLineFactory
from rest_framework import status
from testfixtures import LogCapture

from ecommerce.core.constants import SYSTEM_ENTERPRISE_LEARNER_ROLE
from ecommerce.entitlements.utils import create_or_update_course_entitlement
from ecommerce.extensions.checkout.utils import get_receipt_page_url
from ecommerce.extensions.executive_education_2u.constants import ExecutiveEducation2UCheckoutFailureReason
from ecommerce.extensions.test import factories
from ecommerce.tests.mixins import JwtMixin
from ecommerce.tests.testcases import TestCase

Product = get_model('catalogue', 'Product')
ConditionalOffer = get_model('offer', 'ConditionalOffer')


class ExecutiveEducation2UAPIViewSetTests(TestCase, JwtMixin):

    def setUp(self):
        super().setUp()

        self.mock_settings = {
            'GET_SMARTER_OAUTH2_PROVIDER_URL': 'https://provider-url.com',
            'GET_SMARTER_OAUTH2_KEY': 'key',
            'GET_SMARTER_OAUTH2_SECRET': 'secret',
            'GET_SMARTER_API_URL': 'https://api-url.com',
        }
        self.terms_and_policies_url = f"{self.mock_settings['GET_SMARTER_API_URL']}/terms"

        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)
        self.learner_portal_url = 'http://learner-portal.com'

        self.checkout_path = reverse('executive_education_2u:executive_education_2u-checkout')
        self.enterprise_customer_uuid = uuid4()

        self.set_jwt_cookie(
            system_wide_role=SYSTEM_ENTERPRISE_LEARNER_ROLE, context=str(self.enterprise_customer_uuid)
        )

    def tearDown(self):
        super().tearDown()

    @mock.patch('ecommerce.extensions.executive_education_2u.views.GetSmarterEnterpriseApiClient')
    def test_get_terms_and_policies_200(self, mock_geag_client):
        terms_and_policies = {
            'privacyPolicy': 'abcd',
            'websiteTermsOfUse': 'efgh',
        }

        mock_client = mock.MagicMock()
        mock_geag_client.return_value = mock_client
        mock_client.get_terms_and_policies.return_value = terms_and_policies

        path = reverse('executive_education_2u:executive_education_2u-get-terms-and-policies')

        with self.settings(**self.mock_settings):
            response = self.client.get(path)
            self.assertEqual(status.HTTP_200_OK, response.status_code)
            self.assertEqual(response.json(), terms_and_policies)

    @mock.patch('ecommerce.extensions.executive_education_2u.views.GetSmarterEnterpriseApiClient')
    def test_get_terms_and_policies_500(self, mock_geag_client):
        logger_name = 'ecommerce.extensions.executive_education_2u.views'

        mock_client = mock.MagicMock()
        mock_geag_client.return_value = mock_client
        mock_client.get_terms_and_policies.side_effect = Exception()

        with self.settings(**self.mock_settings), LogCapture(logger_name) as logger:
            path = reverse('executive_education_2u:executive_education_2u-get-terms-and-policies')
            response = self.client.get(path)
            self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
            self.assertEqual(response.json(), 'Failed to retrieve terms and policies.')

    def _create_product(self, is_exec_ed_2u_product=True):
        certificate_type = 'paid-executive-education' if is_exec_ed_2u_product else 'verified'
        product = create_or_update_course_entitlement(
            certificate_type, 100, self.partner, 'product', 'Entitlement Product'
        )
        product.attr.UUID = str(uuid4())
        product.attr.save()
        return product

    def _create_enterprise_offer(self):
        condition = factories.EnterpriseCustomerConditionFactory(
            enterprise_customer_uuid=self.enterprise_customer_uuid
        )
        benefit = factories.EnterprisePercentageDiscountBenefitFactory(value=100)
        offer = factories.EnterpriseOfferFactory(
            benefit=benefit,
            partner=self.partner,
            condition=condition,
            offer_type=ConditionalOffer.SITE
        )
        return offer

    def test_get_checkout_no_sku_400(self):
        response = self.client.get(self.checkout_path)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_checkout_no_exec_ed_product_404(self):
        product = self._create_product(is_exec_ed_2u_product=False)
        sku = product.stockrecords.first().partner_sku

        response = self.client.get(self.checkout_path, {'sku': sku})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_checkout_has_previous_order_redirect_to_receipt_page(self):
        product = self._create_product(is_exec_ed_2u_product=True)
        sku = product.stockrecords.first().partner_sku
        order = OrderFactory(user=self.user)
        OrderLineFactory(order=order, product=product, partner_sku=sku)

        response = self.client.get(self.checkout_path, {'sku': sku})
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)

        expected_redirect_url = get_receipt_page_url(
            response.request,
            order_number=order.number,
            site_configuration=order.site.siteconfiguration,
            disable_back_button=False
        )
        self.assertEqual(response.headers['Location'], expected_redirect_url)

    @mock.patch('ecommerce.enterprise.conditions.catalog_contains_course_runs')
    @mock.patch('ecommerce.enterprise.conditions.get_course_info_from_catalog')
    @mock.patch('ecommerce.extensions.executive_education_2u.views.get_learner_portal_url')
    def test_get_checkout_has_offer_redirect_to_lp(
        self,
        mock_get_learner_portal_url,
        mock_get_course_info_from_catalog,
        mock_catalog_contains_course_runs
    ):
        mock_get_learner_portal_url.return_value = self.learner_portal_url
        product = self._create_product(is_exec_ed_2u_product=True)
        sku = product.stockrecords.first().partner_sku
        self._create_enterprise_offer()

        mock_get_course_info_from_catalog.return_value = {
            'key': product.attr.UUID
        }
        mock_catalog_contains_course_runs.return_value = True

        response = self.client.get(self.checkout_path, {'sku': sku})
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)

        expected_query_params = {
            'course_uuid': product.attr.UUID,
            'sku': sku
        }
        expected_redirect_url = f'{self.learner_portal_url}?{urlencode(expected_query_params)}'
        self.assertEqual(response.headers['Location'], expected_redirect_url)

    @mock.patch('ecommerce.extensions.executive_education_2u.views.get_learner_portal_url')
    def test_get_checkout_no_offer_redirect_to_lp(self, mock_get_learner_portal_url):
        mock_get_learner_portal_url.return_value = self.learner_portal_url
        product = self._create_product(is_exec_ed_2u_product=True)
        sku = product.stockrecords.first().partner_sku

        response = self.client.get(self.checkout_path, {'sku': sku})
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)

        expected_query_params = {
            'course_uuid': product.attr.UUID,
            'sku': sku,
            'failure_reason': ExecutiveEducation2UCheckoutFailureReason.NO_OFFER_AVAILABLE
        }
        expected_redirect_url = f'{self.learner_portal_url}?{urlencode(expected_query_params)}'
        self.assertEqual(response.headers['Location'], expected_redirect_url)
