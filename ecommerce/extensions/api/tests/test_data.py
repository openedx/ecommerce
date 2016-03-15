import json

import httpretty
import mock
import requests
from testfixtures import LogCapture

from ecommerce.core.url_utils import get_lms_url
from ecommerce.extensions.api.data import get_lms_footer
from ecommerce.tests.testcases import TestCase

LOGGER_NAME = 'ecommerce.extensions.api.data'

# TODO: test get_product() and get_order_metadata()


class DataFunctionsTests(TestCase):
    """ Tests for api data functions. """
    def setUp(self):
        super(DataFunctionsTests, self).setUp()
        self.footer_url = get_lms_url('api/branding/v1/footer')

    @httpretty.activate
    def test_get_lms_footer_success(self):
        """ Verify footer information is retrieved. """
        content = {
            'footer': 'edX Footer'
        }
        content_json = json.dumps(content)
        httpretty.register_uri(httpretty.GET, self.footer_url, body=content_json, content_type='application/json')
        response = json.loads(get_lms_footer())
        self.assertEqual(response['footer'], 'edX Footer')

    @httpretty.activate
    def test_get_lms_footer_failure(self):
        """ Verify None is returned on a non-200 status code. """
        httpretty.register_uri(httpretty.GET, self.footer_url, status=404, content_type='application/json')
        response = get_lms_footer()
        self.assertIsNone(response)

    def test_get_lms_footer_conn_error(self):
        """ Verify proper logger message is displayed in case of a connection error. """
        with mock.patch('requests.get', side_effect=requests.exceptions.ConnectionError()):
            with LogCapture(LOGGER_NAME) as l:
                response = get_lms_footer()
                l.check(
                    (
                        LOGGER_NAME, 'ERROR',
                        u'Connection error occurred during getting data for {lms_url} provider'.format(
                            lms_url=get_lms_url()
                        )
                    )
                )
                self.assertIsNone(response)

    def test_get_lms_footer_timeout(self):
        """ Verify proper logger message is displayed in case of a time out. """
        with mock.patch('requests.get', side_effect=requests.Timeout()):
            with LogCapture(LOGGER_NAME) as l:
                response = get_lms_footer()
                l.check(
                    (
                        LOGGER_NAME, 'ERROR',
                        u'Failed to retrieve data for {lms_url} provider, connection timeout'.format(
                            lms_url=get_lms_url()
                        )
                    )
                )
                self.assertIsNone(response)
