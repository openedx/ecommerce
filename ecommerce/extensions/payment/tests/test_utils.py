# -*- coding: utf-8 -*-
import json
from urllib.parse import urljoin

import responses

from ecommerce.extensions.payment.utils import clean_field_value, middle_truncate
from ecommerce.tests.testcases import TestCase


class UtilsTests(TestCase):
    def test_truncation(self):
        """Verify that the truncation utility behaves as expected."""
        length = 10
        test_string = 'x' * length

        # Verify that the original string is returned when no truncation is necessary.
        self.assertEqual(test_string, middle_truncate(test_string, length))
        self.assertEqual(test_string, middle_truncate(test_string, length + 1))

        # Verify that truncation occurs when expected.
        self.assertEqual('xxx...xxx', middle_truncate(test_string, length - 1))
        self.assertEqual('xx...xx', middle_truncate(test_string, length - 2))

        self.assertRaises(ValueError, middle_truncate, test_string, 0)

    def test_clean_field_value(self):
        """ Verify the passed value is cleaned of specific special characters. """
        value = 'Some^text:\'test-value'
        self.assertEqual(clean_field_value(value), 'Sometexttest-value')


class EmbargoCheckTests(TestCase):
    """ Tests for the Embargo check function. """

    @responses.activate
    def setUp(self):
        super(EmbargoCheckTests, self).setUp()
        self.mock_access_token_response()
        self.params = {
            'user': 'foo',
            'ip_address': '0.0.0.0',
            'course_ids': ['foo-course']
        }

    def mock_embargo_response(self, response, status_code=200):
        """ Mock the embargo check API endpoint response. """

        responses.add(
            responses.GET,
            self.site_configuration.build_lms_url('/api/embargo/v1/course_access/'),
            status=status_code,
            body=response,
            content_type='application/json'
        )

    @responses.activate
    def test_embargo_check_match(self):
        """ Verify the embargo check returns False. """
        embargo_response = {'access': False}
        self.mock_access_token_response()
        self.mock_embargo_response(json.dumps(embargo_response))
        client = self.site.siteconfiguration.oauth_api_client
        api_url = urljoin(f"{self.site.siteconfiguration.embargo_api_url}/", "course_access/")
        response = client.get(api_url, params=self.params).json()
        self.assertEqual(response, embargo_response)
