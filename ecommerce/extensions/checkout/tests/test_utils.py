

import ddt
import mock
import requests
import responses
from django.conf import settings
from django.test import override_settings
from django.urls import reverse
from requests import ConnectionError as ReqConnectionError
from requests import Timeout
from waffle.testutils import override_flag

from ecommerce.extensions.api.v2.constants import ENABLE_RECEIPTS_VIA_ECOMMERCE_MFE
from ecommerce.extensions.checkout.utils import get_credit_provider_details, get_receipt_page_url
from ecommerce.tests.testcases import TestCase


@ddt.ddt
class UtilTests(TestCase):
    def setUp(self):
        super(UtilTests, self).setUp()
        self.credit_provider_id = 'HGW'
        self.credit_provider_name = 'Hogwarts'
        self.body = {'display_name': self.credit_provider_name}
        self.order_number = 'EDX-100001'

    def get_credit_provider_details_url(self, credit_provider_id):
        """
        Formats the relative path to the credit provider details API endpoint.

        Args:
            credit_provider_id (str): Credit provider ID for which the details are fetched

        Returns:
            Relative URL to the LMS Credit Provider details API endpoint.
        """
        return 'api/credit/v1/providers/{credit_provider_id}/'.format(credit_provider_id=credit_provider_id)

    @responses.activate
    def test_get_credit_provider_details(self):
        """ Check that credit provider details are returned. """
        self.mock_access_token_response()
        responses.add(
            responses.GET,
            self.site.siteconfiguration.build_lms_url(self.get_credit_provider_details_url(self.credit_provider_id)),
            json=self.body,
            content_type="application/json"
        )
        provider_data = get_credit_provider_details(
            self.credit_provider_id,
            self.site.siteconfiguration
        )
        self.assertDictEqual(provider_data, self.body)

    @responses.activate
    def test_get_credit_provider_details_unavailable_request(self):
        """ Check that None is returned on Bad Request response. """
        responses.add(
            responses.GET,
            self.site.siteconfiguration.build_lms_url(self.get_credit_provider_details_url(self.credit_provider_id)),
            status=400
        )
        provider_data = get_credit_provider_details(
            self.credit_provider_id,
            self.site.siteconfiguration
        )
        self.assertEqual(provider_data, None)

    @ddt.data(ReqConnectionError, Timeout)
    def test_exceptions(self, exception):
        """ Verify the function returns None when a request exception is raised. """
        with mock.patch.object(requests, 'get', mock.Mock(side_effect=exception)):
            self.assertIsNone(
                get_credit_provider_details(
                    self.credit_provider_id,
                    self.site.siteconfiguration
                )
            )

    @override_flag(ENABLE_RECEIPTS_VIA_ECOMMERCE_MFE, active=True)
    def test_get_receipt_page_url_gives_MFE_when_enabled(self):
        """ Verify the function returns the appropriate url when waffle flag is True, False, missing"""

        with override_settings(ECOMMERCE_MICROFRONTEND_URL='http://test.MFE.domain'):
            params = '?order_number=EDX-100001&disable_back_button=1'

            receipt_url = get_receipt_page_url(
                self.request,
                order_number=self.order_number,
                site_configuration=self.site_configuration,
                disable_back_button=True
            )

            self.assertEqual(receipt_url, settings.ECOMMERCE_MICROFRONTEND_URL + '/receipt/' + params)

    @override_flag(ENABLE_RECEIPTS_VIA_ECOMMERCE_MFE, active=False)
    def test_get_receipt_page_url_gives_ecommerce_if_no_waffle(self):
        """ Verify the function returns the appropriate url when waffle flag is True, False, missing"""

        with override_settings(ECOMMERCE_MICROFRONTEND_URL='http://test.MFE.domain'):
            params = '?order_number=EDX-100001&disable_back_button=1'

            receipt_url = get_receipt_page_url(
                self.request,
                order_number=self.order_number,
                site_configuration=self.site_configuration,
                disable_back_button=True
            )

            self.assertEqual(receipt_url, self.site_configuration.build_ecommerce_url(reverse('checkout:receipt')) +
                             params)
