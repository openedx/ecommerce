from urllib.parse import urlencode
from uuid import uuid4

import mock
from django.urls import reverse
from oscar.core.loading import get_model
from oscar.test.factories import OrderDiscountFactory, OrderFactory, OrderLineFactory
from rest_framework import status

from ecommerce.core.constants import SYSTEM_ENTERPRISE_LEARNER_ROLE
from ecommerce.courses.constants import CertificateType
from ecommerce.entitlements.utils import create_or_update_course_entitlement
from ecommerce.extensions.checkout.utils import get_receipt_page_url
from ecommerce.extensions.executive_education_2u.constants import ExecutiveEducation2UCheckoutFailureReason
from ecommerce.extensions.executive_education_2u.utils import get_previous_order_for_user
from ecommerce.extensions.fulfillment.status import ORDER
from ecommerce.extensions.refund.status import REFUND
from ecommerce.extensions.refund.tests.factories import RefundFactory
from ecommerce.extensions.test import factories
from ecommerce.tests.mixins import JwtMixin
from ecommerce.tests.testcases import TestCase

Product = get_model('catalogue', 'Product')
ConditionalOffer = get_model('offer', 'ConditionalOffer')
Basket = get_model('basket', 'Basket')


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

        self.checkout_path = reverse('executive_education_2u:executive_education_2u-begin-checkout')
        self.enterprise_customer_uuid = uuid4()

        self.set_jwt_cookie(
            system_wide_role=SYSTEM_ENTERPRISE_LEARNER_ROLE, context=str(self.enterprise_customer_uuid)
        )

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
        mock_client = mock.MagicMock()
        mock_geag_client.return_value = mock_client
        mock_client.get_terms_and_policies.side_effect = Exception()

        with self.settings(**self.mock_settings):
            path = reverse('executive_education_2u:executive_education_2u-get-terms-and-policies')
            response = self.client.get(path)
            self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
            self.assertEqual(response.json(), 'Failed to retrieve terms and policies.')

    def _create_product(self, is_exec_ed_2u_product=True):
        certificate_type = CertificateType.PAID_EXECUTIVE_EDUCATION if is_exec_ed_2u_product \
            else CertificateType.VERIFIED
        product = create_or_update_course_entitlement(
            certificate_type, 100, self.partner, 'product', 'Entitlement Product'
        )
        product.attr.UUID = str(uuid4())
        product.attr.save()
        return product

    def _create_enterprise_offer(self, max_discount=None, max_user_discount=None, **kwargs):
        condition = factories.EnterpriseCustomerConditionFactory(
            enterprise_customer_uuid=self.enterprise_customer_uuid
        )
        benefit = factories.EnterprisePercentageDiscountBenefitFactory(value=100)
        offer = factories.EnterpriseOfferFactory(
            benefit=benefit,
            partner=self.partner,
            condition=condition,
            offer_type=ConditionalOffer.SITE,
            max_discount=max_discount,
            max_user_discount=max_user_discount,
            **kwargs,
        )
        return offer

    def test_begin_checkout_no_sku_400(self):
        response = self.client.get(self.checkout_path)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_begin_checkout_no_exec_ed_product_404(self):
        product = self._create_product(is_exec_ed_2u_product=False)
        sku = product.stockrecords.first().partner_sku

        response = self.client.get(self.checkout_path, {'sku': sku})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_begin_checkout_has_previous_order_redirect_to_receipt_page(self):
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

    def test_begin_checkout_has_previous_order_refund_error_redirect_to_receipt_page(self):
        product = self._create_product(is_exec_ed_2u_product=True)
        sku = product.stockrecords.first().partner_sku
        order = OrderFactory(user=self.user)
        OrderLineFactory(order=order, product=product, partner_sku=sku)
        RefundFactory(order=order, user=self.user, status=REFUND.PAYMENT_REFUND_ERROR)

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
    def test_begin_checkout_has_previous_refunded_order_redirect_to_lp(
        self,
        mock_get_learner_portal_url,
        mock_get_course_info_from_catalog,
        mock_catalog_contains_course_runs
    ):
        mock_get_learner_portal_url.return_value = self.learner_portal_url
        product = self._create_product(is_exec_ed_2u_product=True)
        sku = product.stockrecords.first().partner_sku
        self._create_enterprise_offer()

        order = OrderFactory(user=self.user)
        OrderLineFactory(order=order, product=product, partner_sku=sku)
        RefundFactory(order=order, user=self.user, status=REFUND.COMPLETE)

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
        expected_redirect_url = f'{self.learner_portal_url}/executive-education-2u?{urlencode(expected_query_params)}'
        self.assertEqual(response.headers['Location'], expected_redirect_url)

    @mock.patch('ecommerce.enterprise.conditions.catalog_contains_course_runs')
    @mock.patch('ecommerce.enterprise.conditions.get_course_info_from_catalog')
    @mock.patch('ecommerce.extensions.executive_education_2u.views.get_learner_portal_url')
    def test_begin_checkout_has_offer_redirect_to_lp(
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
        expected_redirect_url = f'{self.learner_portal_url}/executive-education-2u?{urlencode(expected_query_params)}'
        self.assertEqual(response.headers['Location'], expected_redirect_url)

    @mock.patch('ecommerce.extensions.executive_education_2u.views.fetch_enterprise_catalogs_for_content_items')
    @mock.patch('ecommerce.extensions.executive_education_2u.views.get_course_info_from_catalog')
    @mock.patch('ecommerce.extensions.executive_education_2u.views.get_learner_portal_url')
    def test_begin_checkout_no_offer(
        self,
        mock_get_learner_portal_url,
        mock_get_course_info_from_catalog,
        mock_fetch_enterprise_catalogs_for_content_items
    ):
        mock_get_learner_portal_url.return_value = self.learner_portal_url
        mock_fetch_enterprise_catalogs_for_content_items.return_value = []
        product = self._create_product(is_exec_ed_2u_product=True)
        sku = product.stockrecords.first().partner_sku
        mock_get_course_info_from_catalog.return_value = {
            'key': product.attr.UUID
        }

        response = self.client.get(self.checkout_path, {'sku': sku})
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)

        expected_query_params = {
            'course_uuid': product.attr.UUID,
            'sku': sku,
            'failure_reason': ExecutiveEducation2UCheckoutFailureReason.NO_OFFER_AVAILABLE
        }
        expected_redirect_url = f'{self.learner_portal_url}/executive-education-2u?{urlencode(expected_query_params)}'
        self.assertEqual(response.headers['Location'], expected_redirect_url)

    @mock.patch('ecommerce.extensions.executive_education_2u.views.fetch_enterprise_catalogs_for_content_items')
    @mock.patch('ecommerce.extensions.executive_education_2u.views.get_course_info_from_catalog')
    @mock.patch('ecommerce.extensions.executive_education_2u.views.get_learner_portal_url')
    def test_begin_checkout_no_offer_with_enough_balance(
        self,
        mock_get_learner_portal_url,
        mock_get_course_info_from_catalog,
        mock_fetch_enterprise_catalogs_for_content_items
    ):
        mock_get_learner_portal_url.return_value = self.learner_portal_url
        offer = self._create_enterprise_offer(max_discount=50)
        mock_fetch_enterprise_catalogs_for_content_items.return_value = [
            offer.condition.enterprise_customer_catalog_uuid
        ]
        product = self._create_product(is_exec_ed_2u_product=True)
        sku = product.stockrecords.first().partner_sku
        mock_get_course_info_from_catalog.return_value = {
            'key': product.attr.UUID
        }

        response = self.client.get(self.checkout_path, {'sku': sku})
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)

        expected_query_params = {
            'course_uuid': product.attr.UUID,
            'sku': sku,
            'failure_reason': ExecutiveEducation2UCheckoutFailureReason.NO_OFFER_WITH_ENOUGH_BALANCE
        }
        expected_redirect_url = f'{self.learner_portal_url}/executive-education-2u?{urlencode(expected_query_params)}'
        self.assertEqual(response.headers['Location'], expected_redirect_url)

    @mock.patch('ecommerce.extensions.executive_education_2u.views.fetch_enterprise_catalogs_for_content_items')
    @mock.patch('ecommerce.extensions.executive_education_2u.views.get_course_info_from_catalog')
    @mock.patch('ecommerce.extensions.executive_education_2u.views.get_learner_portal_url')
    def test_begin_checkout_no_offer_with_enough_user_balance(
        self,
        mock_get_learner_portal_url,
        mock_get_course_info_from_catalog,
        mock_fetch_enterprise_catalogs_for_content_items
    ):
        mock_get_learner_portal_url.return_value = self.learner_portal_url
        offer = self._create_enterprise_offer(max_user_discount=100)
        mock_fetch_enterprise_catalogs_for_content_items.return_value = [
            offer.condition.enterprise_customer_catalog_uuid
        ]
        product = self._create_product(is_exec_ed_2u_product=True)
        sku = product.stockrecords.first().partner_sku
        mock_get_course_info_from_catalog.return_value = {
            'key': product.attr.UUID
        }

        # Create order discounts
        order = OrderFactory(user=self.user, status=ORDER.COMPLETE)
        OrderDiscountFactory(order=order, offer_id=offer.id, amount=50)

        response = self.client.get(self.checkout_path, {'sku': sku})
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)

        expected_query_params = {
            'course_uuid': product.attr.UUID,
            'sku': sku,
            'failure_reason': ExecutiveEducation2UCheckoutFailureReason.NO_OFFER_WITH_ENOUGH_USER_BALANCE
        }
        expected_redirect_url = f'{self.learner_portal_url}/executive-education-2u?{urlencode(expected_query_params)}'
        self.assertEqual(response.headers['Location'], expected_redirect_url)

    @mock.patch('ecommerce.extensions.executive_education_2u.views.fetch_enterprise_catalogs_for_content_items')
    @mock.patch('ecommerce.extensions.executive_education_2u.views.get_course_info_from_catalog')
    @mock.patch('ecommerce.extensions.executive_education_2u.views.get_learner_portal_url')
    def test_begin_checkout_no_offer_with_remaining_applications(
        self,
        mock_get_learner_portal_url,
        mock_get_course_info_from_catalog,
        mock_fetch_enterprise_catalogs_for_content_items
    ):
        mock_get_learner_portal_url.return_value = self.learner_portal_url
        offer = self._create_enterprise_offer(max_user_applications=1)
        mock_fetch_enterprise_catalogs_for_content_items.return_value = [
            offer.condition.enterprise_customer_catalog_uuid
        ]
        product = self._create_product(is_exec_ed_2u_product=True)
        sku = product.stockrecords.first().partner_sku
        mock_get_course_info_from_catalog.return_value = {
            'key': product.attr.UUID
        }

        # Create order discounts
        order = OrderFactory(user=self.user, status=ORDER.COMPLETE)
        OrderDiscountFactory(order=order, offer_id=offer.id, frequency=1)

        response = self.client.get(self.checkout_path, {'sku': sku})
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)

        expected_query_params = {
            'course_uuid': product.attr.UUID,
            'sku': sku,
            'failure_reason': ExecutiveEducation2UCheckoutFailureReason.NO_OFFER_WITH_REMAINING_APPLICATIONS
        }
        expected_redirect_url = f'{self.learner_portal_url}/executive-education-2u?{urlencode(expected_query_params)}'
        self.assertEqual(response.headers['Location'], expected_redirect_url)

    @mock.patch('ecommerce.extensions.executive_education_2u.views.get_course_info_from_catalog')
    @mock.patch('ecommerce.extensions.executive_education_2u.views.get_learner_portal_url')
    def test_begin_checkout_system_error(
        self,
        mock_get_learner_portal_url,
        mock_get_course_info_from_catalog
    ):
        mock_get_learner_portal_url.return_value = self.learner_portal_url
        product = self._create_product(is_exec_ed_2u_product=True)
        sku = product.stockrecords.first().partner_sku
        mock_get_course_info_from_catalog.side_effect = Exception()

        response = self.client.get(self.checkout_path, {'sku': sku})
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)

        expected_query_params = {
            'course_uuid': product.attr.UUID,
            'sku': sku,
            'failure_reason': ExecutiveEducation2UCheckoutFailureReason.SYSTEM_ERROR
        }
        expected_redirect_url = f'{self.learner_portal_url}/executive-education-2u?{urlencode(expected_query_params)}'
        self.assertEqual(response.headers['Location'], expected_redirect_url)

    def _create_finish_checkout_payload(self, sku):
        return {
            'sku': sku,
            'address': {
                'address_line1': '10 Lovely Street',
                'city': 'Herndon',
                'postal_code': '00000',
                'state': 'state',
                'state_code': 'state_code',
                'country': 'country',
                'country_code': 'country_code',
            },
            'user_details': {
                'first_name': 'John',
                'last_name': 'Smith',
                'date_of_birth': '2000-01-01',
                'mobile_phone': '1234567890'
            },
            'terms_accepted_at': '2022-08-05T15:28:46.493Z',
            'data_share_consent': True,
        }

    def _create_basket(self, product, has_offer=False):
        if has_offer:
            self._create_enterprise_offer()

        basket = Basket.get_basket(self.user, self.site)
        basket.add_product(product, 1)
        return basket

    def test_finish_checkout_no_product_for_sku_400(
        self
    ):
        sku = 'abc'
        payload = self._create_finish_checkout_payload(sku)
        response = self.client.post(self.checkout_path, payload, 'application/json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.json(), f'No Executive Education (2U) product found for SKU {sku}.')

    @mock.patch('ecommerce.enterprise.conditions.catalog_contains_course_runs')
    @mock.patch('ecommerce.enterprise.conditions.get_course_info_from_catalog')
    def test_finish_checkout_has_previous_order_422(
        self,
        mock_get_course_info_from_catalog,
        mock_catalog_contains_course_runs
    ):
        product = self._create_product(is_exec_ed_2u_product=True)
        mock_get_course_info_from_catalog.return_value = {
            'key': product.attr.UUID
        }
        mock_catalog_contains_course_runs.return_value = True

        sku = product.stockrecords.first().partner_sku
        order = OrderFactory(user=self.user)
        OrderLineFactory(order=order, product=product, partner_sku=sku)

        self._create_basket(product, has_offer=True)

        payload = self._create_finish_checkout_payload(sku)
        response = self.client.post(self.checkout_path, payload, 'application/json')
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(response.json(), 'User has already purchased the product.')

    @mock.patch('ecommerce.enterprise.conditions.catalog_contains_course_runs')
    @mock.patch('ecommerce.enterprise.conditions.get_course_info_from_catalog')
    def test_finish_checkout_place_order_no_offer_422(
        self,
        mock_get_course_info_from_catalog,
        mock_catalog_contains_course_runs
    ):
        product = self._create_product(is_exec_ed_2u_product=True)
        sku = product.stockrecords.first().partner_sku
        mock_get_course_info_from_catalog.return_value = {
            'key': product.attr.UUID
        }
        mock_catalog_contains_course_runs.return_value = True
        self._create_basket(product, has_offer=False)

        payload = self._create_finish_checkout_payload(sku)
        response = self.client.post(self.checkout_path, payload, 'application/json')
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(response.json(), 'Failed to create subsidized order.')

    @mock.patch('ecommerce.enterprise.conditions.catalog_contains_course_runs')
    @mock.patch('ecommerce.enterprise.conditions.get_course_info_from_catalog')
    def test_finish_checkout_place_order_200(
        self,
        mock_get_course_info_from_catalog,
        mock_catalog_contains_course_runs
    ):
        product = self._create_product(is_exec_ed_2u_product=True)
        sku = product.stockrecords.first().partner_sku
        mock_get_course_info_from_catalog.return_value = {
            'key': product.attr.UUID
        }
        mock_catalog_contains_course_runs.return_value = True
        self._create_basket(product, has_offer=True)

        payload = self._create_finish_checkout_payload(sku)
        response = self.client.post(self.checkout_path, payload, 'application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        order = get_previous_order_for_user(self.user, product)
        self.assertEqual(order.lines.first().product, product)

        expected_redirect_url = get_receipt_page_url(
            response.request,
            order_number=order.number,
            site_configuration=order.site.siteconfiguration,
            disable_back_button=False
        )
        self.assertEqual(response.json()['receipt_page_url'], expected_redirect_url)
