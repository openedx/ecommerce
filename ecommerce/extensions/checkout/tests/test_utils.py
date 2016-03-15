import ddt
import httpretty
import mock
import requests
from requests import ConnectionError, Timeout

from ecommerce.core.url_utils import get_lms_url
from ecommerce.extensions.checkout.utils import get_provider_data
from ecommerce.tests.testcases import TestCase


@ddt.ddt
class UtilTests(TestCase):
    @httpretty.activate
    def test_get_provider_data(self):
        """
        Check if correct data returns on the full filled request.
        """
        httpretty.register_uri(
            httpretty.GET, get_lms_url('api/credit/v1/providers/ASU'),
            body='{"display_name": "Arizona State University"}',
            content_type="application/json"
        )
        provider_data = get_provider_data('ASU')
        self.assertDictEqual(provider_data, {"display_name": "Arizona State University"})

    @httpretty.activate
    def test_get_provider_data_unavailable_request(self):
        """
        Check if None return on the bad request
        """
        httpretty.register_uri(
            httpretty.GET, get_lms_url('api/credit/v1/providers/ABC'),
            status=400
        )
        provider_data = get_provider_data('ABC')
        self.assertEqual(provider_data, None)

    @ddt.data(ConnectionError, Timeout)
    def test_exceptions(self, exception):
        """ Verify the function returns None when a request exception is raised. """
        with mock.patch.object(requests, 'get', mock.Mock(side_effect=exception)):
            self.assertIsNone(get_provider_data('ABC'))
