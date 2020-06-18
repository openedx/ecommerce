

import json

import ddt
import httpretty
import mock
import requests
from requests import ConnectionError as ReqConnectionError
from requests import Timeout

from ecommerce.extensions.checkout.utils import get_credit_provider_details
from ecommerce.tests.testcases import TestCase


@ddt.ddt
class UtilTests(TestCase):
    def setUp(self):
        super(UtilTests, self).setUp()
        self.credit_provider_id = 'HGW'
        self.credit_provider_name = 'Hogwarts'
        self.body = {'display_name': self.credit_provider_name}

    def get_credit_provider_details_url(self, credit_provider_id):
        """
        Formats the relative path to the credit provider details API endpoint.

        Args:
            credit_provider_id (str): Credit provider ID for which the details are fetched

        Returns:
            Relative URL to the LMS Credit Provider details API endpoint.
        """
        return 'api/credit/v1/providers/{credit_provider_id}/'.format(credit_provider_id=credit_provider_id)

    @httpretty.activate
    def test_get_credit_provider_details(self):
        """ Check that credit provider details are returned. """
        self.mock_access_token_response()
        httpretty.register_uri(
            httpretty.GET,
            self.site.siteconfiguration.build_lms_url(self.get_credit_provider_details_url(self.credit_provider_id)),
            body=json.dumps(self.body),
            content_type="application/json"
        )
        provider_data = get_credit_provider_details(
            self.credit_provider_id,
            self.site.siteconfiguration
        )
        self.assertDictEqual(provider_data, self.body)

    @httpretty.activate
    def test_get_credit_provider_details_unavailable_request(self):
        """ Check that None is returned on Bad Request response. """
        httpretty.register_uri(
            httpretty.GET,
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
