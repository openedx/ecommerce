

from django.conf import settings
from django.test import override_settings
from django.urls import reverse

from ecommerce.extensions.payment.tests.views.test_cybersource import LoginMixin
from ecommerce.tests.testcases import TestCase


class ApplePayMerchantDomainAssociationViewTests(LoginMixin, TestCase):
    url = reverse('apple_pay_domain_association')

    def setUp(self):
        super(ApplePayMerchantDomainAssociationViewTests, self).setUp()
        self.site_configuration.client_side_payment_processor = 'cybersource'
        self.site_configuration.save()

    def set_apple_pay_merchant_id_domain_association(self, value):
        key = 'apple_pay_merchant_id_domain_association'
        partner_code = self.site_configuration.partner.short_code
        processor_name = self.site_configuration.client_side_payment_processor
        settings.PAYMENT_PROCESSOR_CONFIG[partner_code][processor_name][key] = value

    def assert_response_matches(self, response, expected_status_code, expected_content):
        self.assertEqual(response.status_code, expected_status_code)
        self.assertEqual(response.content.decode('utf-8'), expected_content)
        self.assertEqual(response['Content-Type'], 'text/plain')

    @override_settings()
    def test_get(self):
        """ The view should return the the merchant domain association verification data. """
        expected = 'fake-value'
        self.set_apple_pay_merchant_id_domain_association(expected)
        response = self.client.get(self.url)
        self.assert_response_matches(response, 200, expected)

    @override_settings()
    def test_get_with_configuration_error(self):
        """ The view should return HTTP 501 if Apple Pay is not properly configured. """
        self.set_apple_pay_merchant_id_domain_association(None)
        response = self.client.get(self.url)
        content = 'Apple Pay is not configured for [{}].'.format(self.site.domain)
        self.assert_response_matches(response, 501, content)
