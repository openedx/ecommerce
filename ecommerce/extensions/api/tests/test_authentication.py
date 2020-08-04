# -*- coding: utf-8 -*-


import json
from urllib.parse import urljoin

import httpretty
import mock
from django.test import RequestFactory

from ecommerce.extensions.api.authentication import BearerAuthentication
from ecommerce.tests.testcases import TestCase


class AccessTokenMixin:
    DEFAULT_TOKEN = 'abc123'
    JSON = 'application/json'

    def mock_user_info_response(self, status=200, username='fake-user'):
        data = {
            'preferred_username': username,
            'email': '{}@example.com'.format(username),
            'family_name': 'Doe',
            'given_name': 'Jane',
        }
        url = '{}/user_info/'.format(self.site.siteconfiguration.oauth2_provider_url)
        httpretty.register_uri(httpretty.GET, url, body=json.dumps(data), content_type=self.JSON, status=status)


class BearerAuthenticationTests(TestCase):
    """ Tests for the BearerAuthentication class. """

    def setUp(self):
        super(BearerAuthenticationTests, self).setUp()
        self.auth = BearerAuthentication()
        self.factory = RequestFactory()

    def create_request(self, token=AccessTokenMixin.DEFAULT_TOKEN):
        """ Returns a Request with the correct authorization header and Site. """
        auth_header = 'Bearer {}'.format(token)
        request = self.factory.get('/', HTTP_AUTHORIZATION=auth_header)
        request.site = self.site
        return request

    def test_get_user_info_url(self):
        """ Verify the method returns a user info URL specific to the Site's LMS instance. """
        request = self.create_request()
        with mock.patch('ecommerce.extensions.order.utils.get_current_request', mock.Mock(return_value=request)):
            actual = self.auth.get_user_info_url()
            expected = urljoin(self.site.siteconfiguration.lms_url_root, '/oauth2/user_info/')
            self.assertEqual(actual, expected)
