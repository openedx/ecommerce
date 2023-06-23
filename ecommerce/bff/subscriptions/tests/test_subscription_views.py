import json
import uuid
from unittest import mock

from django.urls import reverse
from oscar.core.loading import get_model
from oscar.test.factories import ProductFactory
from rest_framework import status

from ecommerce.core.constants import COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME
from ecommerce.core.models import SiteConfiguration
from ecommerce.coupons.tests.mixins import DiscoveryMockMixin
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.tests.factories import ProductFactory
from ecommerce.tests.testcases import TestCase

Catalog = get_model('catalogue', 'Catalog')
StockRecord = get_model('partner', 'StockRecord')
Product = get_model('catalogue', 'Product')
ProductClass = get_model('catalogue', 'ProductClass')


class ProductEntitlementInfoViewTestCase(DiscoveryTestMixin, DiscoveryMockMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.user = self.create_user(is_staff=True)
        self.client.login(username=self.user.username, password=self.password)
        self.ip_address = "mock_address"

        site_configuration = SiteConfiguration.objects.get(site=self.site)
        site_configuration.enable_embargo_check = True
        site_configuration.save()

    @mock.patch('ecommerce.bff.subscriptions.views.embargo_check')
    def test_with_skus(self, mock_embargo_check):
        mock_embargo_check.return_value = True
        product_class, _ = ProductClass.objects.get_or_create(name=COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME)

        product1 = ProductFactory(title="test product 1", product_class=product_class, stockrecords__partner=self.partner)
        product1.attr.UUID = str(uuid.uuid4())
        product1.attr.certificate_type = 'verified'
        product1.attr.id_verification_required = False

        product2 = ProductFactory(title="test product 2", product_class=product_class, stockrecords__partner=self.partner)
        product2.attr.UUID = str(uuid.uuid4())
        product2.attr.certificate_type = 'professional'
        product2.attr.id_verification_required = True

        product1.attr.save()
        product2.attr.save()
        product1.refresh_from_db()
        product2.refresh_from_db()

        url = reverse('bff:subscriptions:product-entitlement-info')

        response = self.client.post(url, data={'skus': [product1.stockrecords.first().partner_sku,
                                                        product2.stockrecords.first().partner_sku],
                                               'user_ip_address': self.ip_address, 'username': self.user.username
                                               })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected_data = {'data': [
            {'course_uuid': product1.attr.UUID, 'mode': product1.attr.certificate_type,
             'sku': product1.stockrecords.first().partner_sku},
            {'course_uuid': product2.attr.UUID, 'mode': product2.attr.certificate_type,
             'sku': product2.stockrecords.first().partner_sku},
        ]}
        self.assertCountEqual(json.loads(response.content.decode('utf-8')), expected_data)

    @mock.patch('ecommerce.bff.subscriptions.views.logger.error')
    def test_with_valid_and_invalid_products(self, mock_log):
        product_class, _ = ProductClass.objects.get_or_create(name=COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME)

        product1 = ProductFactory(title="test product 1", product_class=product_class, stockrecords__partner=self.partner)
        product1.attr.UUID = str(uuid.uuid4())
        product1.attr.certificate_type = 'verified'
        product1.attr.id_verification_required = False

        # product2 is invalid because it does not have either one or both of UUID and certificate_type
        product2 = ProductFactory(title="test product 2", product_class=product_class, stockrecords__partner=self.partner)

        product1.attr.save()
        product1.refresh_from_db()

        url = reverse('bff:subscriptions:product-entitlement-info')

        response = self.client.post(url, data={'skus': [product1.stockrecords.first().partner_sku,
                                                        product2.stockrecords.first().partner_sku],
                                               'user_ip_address': self.ip_address, 'username': self.user.username
                                               })

        mock_log.assert_called_once_with(f"B2C_SUBSCRIPTIONS: Product {product2}"
                                         f" does not have a UUID attribute or mode is None")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected_data = {'data': [
            {'course_uuid': product1.attr.UUID, 'mode': product1.attr.certificate_type,
             'sku': product1.stockrecords.first().partner_sku}
        ]}
        self.assertCountEqual(json.loads(response.content.decode('utf-8')), expected_data)

    def test_with_invalid_sku(self):
        url = reverse('bff:subscriptions:product-entitlement-info')
        response = self.client.post(url, data={'skus': ["blah", "blah-2"],
                                               'user_ip_address': self.ip_address, 'username': self.user.username
                                               })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        expected_data = {'error': 'Products with SKU(s) [blah, blah-2] do not exist.'}
        self.assertCountEqual(json.loads(response.content.decode('utf-8')), expected_data)

    def test_with_empty_sku(self):
        url = reverse('bff:subscriptions:product-entitlement-info')
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        expected_data = {'error': 'No SKUs provided.'}
        self.assertCountEqual(json.loads(response.content.decode('utf-8')), expected_data)

    @mock.patch('ecommerce.bff.subscriptions.views.embargo_check')
    def test_embargo_failure(self, mock_embargo_check):
        # In actual we don't expect Embargo to be False for any COURSE ENTITLEMENT product
        # in its current Implementation. But we are mocking it to test the failure case.
        # This will be fixed as a result of https://2u-internal.atlassian.net/browse/REV-3559

        mock_embargo_check.return_value = False
        product_class, _ = ProductClass.objects.get_or_create(name=COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME)

        product1 = ProductFactory(title="test product 1", product_class=product_class, stockrecords__partner=self.partner)
        product1.attr.UUID = str(uuid.uuid4())
        product1.attr.certificate_type = 'verified'
        product1.attr.id_verification_required = False

        product1.attr.save()
        product1.refresh_from_db()

        url = reverse('bff:subscriptions:product-entitlement-info')

        response = self.client.post(url, data={'skus': [product1.stockrecords.first().partner_sku],
                                               'user_ip_address': self.ip_address, 'username': self.user.username
                                               })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected_data = {'error': 'User blocked by embargo check', 'error_code': 'embargo_failed'}
        self.assertCountEqual(json.loads(response.content.decode('utf-8')), expected_data)
