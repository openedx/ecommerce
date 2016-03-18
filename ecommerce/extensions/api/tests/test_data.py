import json

import httpretty
import mock
import requests

from ecommerce.core.url_utils import get_lms_url
from ecommerce.extensions.api.data import get_lms_footer
from ecommerce.tests.testcases import TestCase

# TODO: test get_product() and get_order_metadata()


class DataFunctionsTests(TestCase):
    """Tests for API data helpers."""
    def setUp(self):
        super(DataFunctionsTests, self).setUp()
        self.footer_url = get_lms_url('api/branding/v1/footer')

    @httpretty.activate
    def test_get_lms_footer_success(self):
        """Verify footer information is retrieved."""
        content = {
            'footer': 'edX Footer'
        }
        content_json = json.dumps(content)
        httpretty.register_uri(httpretty.GET, self.footer_url, body=content_json, content_type='application/json')
        response = json.loads(get_lms_footer())
        self.assertEqual(response['footer'], 'edX Footer')

    @httpretty.activate
    def test_get_lms_footer_failure(self):
        """Verify None is returned on a non-200 status code while retrieving LMS footer."""
        httpretty.register_uri(httpretty.GET, self.footer_url, status=404, content_type='application/json')
        response = get_lms_footer()
        self.assertIsNone(response)

    def test_get_lms_footer_connection_error(self):
        """Verify behavior in the event of a connection error while retrieving LMS footer."""
        with mock.patch('requests.get', side_effect=requests.exceptions.ConnectionError()):
            with mock.patch('ecommerce.extensions.api.data.logger.exception') as mock_logger:
                response = get_lms_footer()

                self.assertTrue(mock_logger.called)
                self.assertIsNone(response)

    def test_get_lms_footer_timeout(self):
        """Verify behavior in the event of a timeout while retrieving LMS footer."""
        with mock.patch('requests.get', side_effect=requests.Timeout()):
            with mock.patch('ecommerce.extensions.api.data.logger.exception') as mock_logger:
                response = get_lms_footer()

                self.assertTrue(mock_logger.called)
                self.assertIsNone(response)
