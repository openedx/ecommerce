# -*- coding: utf-8 -*-
import json
import time
from urllib import urlencode

import httpretty
import mock
from django.conf import settings
from django.test import override_settings
from oscar.test import factories
from requests.exceptions import HTTPError, Timeout

from ecommerce.core.models import User
from ecommerce.extensions.payment.models import SDNCheckFailure
from ecommerce.extensions.payment.utils import SDNClient, clean_field_value, middle_truncate
from ecommerce.tests.testcases import TestCase


class UtilsTests(TestCase):
    def test_truncation(self):
        """Verify that the truncation utility behaves as expected."""
        length = 10
        string = 'x' * length

        # Verify that the original string is returned when no truncation is necessary.
        self.assertEqual(string, middle_truncate(string, length))
        self.assertEqual(string, middle_truncate(string, length + 1))

        # Verify that truncation occurs when expected.
        self.assertEqual('xxx...xxx', middle_truncate(string, length - 1))
        self.assertEqual('xx...xx', middle_truncate(string, length - 2))

        self.assertRaises(ValueError, middle_truncate, string, 0)

    def test_clean_field_value(self):
        """ Verify the passed value is cleaned of specific special characters. """
        value = 'Some^text:\'test-value'
        self.assertEqual(clean_field_value(value), 'Sometexttest-value')


class SDNCheckTests(TestCase):
    """ Tests for the SDN check function. """

    def setUp(self):
        super(SDNCheckTests, self).setUp()
        self.name = 'Dr. Evil'
        self.city = 'Top-secret lair'
        self.country = 'EL'
        self.user = self.create_user(full_name=self.name)
        self.site_configuration = self.site.siteconfiguration
        self.site_configuration.enable_sdn_check = True
        self.site_configuration.sdn_api_url = 'http://sdn-test.fake/'
        self.site_configuration.sdn_api_key = 'fake-key'
        self.site_configuration.sdn_api_list = 'SDN,TEST'
        self.site_configuration.save()

        self.sdn_validator = SDNClient(
            self.site_configuration.sdn_api_url,
            self.site_configuration.sdn_api_key,
            self.site_configuration.sdn_api_list
        )

    def mock_sdn_response(self, response, status_code=200):
        """ Mock the SDN check API endpoint response. """
        params = urlencode({
            'sources': self.site_configuration.sdn_api_list,
            'api_key': self.site_configuration.sdn_api_key,
            'type': 'individual',
            'name': unicode(self.name).encode('utf-8'),
            'address': unicode(self.city).encode('utf-8'),
            'countries': self.country
        })
        sdn_check_url = '{api_url}?{params}'.format(
            api_url=self.site_configuration.sdn_api_url,
            params=params
        )

        httpretty.register_uri(
            httpretty.GET,
            sdn_check_url,
            status=status_code,
            body=response,
            content_type='application/json'
        )

    @httpretty.activate
    @override_settings(SDN_CHECK_REQUEST_TIMEOUT=0.1)
    def test_sdn_check_timeout(self):
        """Verify SDN check logs an exception if the request times out."""
        def mock_timeout(_request, _uri, headers):
            time.sleep(settings.SDN_CHECK_REQUEST_TIMEOUT + 0.1)
            return (200, headers, {'total': 1})

        self.mock_sdn_response(mock_timeout, status_code=200)
        with self.assertRaises(Timeout):
            with mock.patch('ecommerce.extensions.payment.utils.logger.exception') as mock_logger:
                self.sdn_validator.search(self.name, self.city, self.country)
                self.assertTrue(mock_logger.called)

    @httpretty.activate
    def test_sdn_check_connection_error(self):
        """ Verify the check logs an exception in case of a connection error. """
        self.mock_sdn_response(json.dumps({'total': 1}), status_code=400)
        with self.assertRaises(HTTPError):
            with mock.patch('ecommerce.extensions.payment.utils.logger.exception') as mock_logger:
                self.sdn_validator.search(self.name, self.city, self.country)
                self.assertTrue(mock_logger.called)

    @httpretty.activate
    def test_sdn_check_match(self):
        """ Verify the SDN check returns the number of matches and records the match. """
        sdn_response = {'total': 1}
        self.mock_sdn_response(json.dumps(sdn_response))
        response = self.sdn_validator.search(self.name, self.city, self.country)
        self.assertEqual(response, sdn_response)

    @httpretty.activate
    def test_sdn_check_unicode_match(self):
        """ Verify the SDN check returns the number of matches and records the match. """
        sdn_response = {'total': 1}
        self.name = u'Keyser Söze'
        self.mock_sdn_response(json.dumps(sdn_response))
        response = self.sdn_validator.search(self.name, self.city, self.country)
        self.assertEqual(response, sdn_response)

    def test_deactivate_user(self):
        """ Verify an SDN failure is logged. """
        response = {'description': 'Bad dude.'}
        product1 = factories.ProductFactory(stockrecords__partner__short_code='first')
        product2 = factories.ProductFactory(stockrecords__partner__short_code='second')
        basket = factories.BasketFactory(owner=self.user, site=self.site_configuration.site)
        basket.add(product1)
        basket.add(product2)
        self.assertEqual(SDNCheckFailure.objects.count(), 0)
        with mock.patch.object(User, 'deactivate_account') as deactivate_account:
            deactivate_account.return_value = True
            self.sdn_validator.deactivate_user(
                basket,
                self.name,
                self.city,
                self.country,
                response
            )

            self.assertEqual(SDNCheckFailure.objects.count(), 1)
            sdn_object = SDNCheckFailure.objects.first()
            self.assertEqual(sdn_object.full_name, self.name)
            self.assertEqual(sdn_object.city, self.city)
            self.assertEqual(sdn_object.country, self.country)
            self.assertEqual(sdn_object.site, self.site_configuration.site)
            self.assertEqual(sdn_object.sdn_check_response, response)
            self.assertEqual(sdn_object.products.count(), basket.lines.count())
            self.assertIn(product1, sdn_object.products.all())
            self.assertIn(product2, sdn_object.products.all())


class EmbargoCheckTests(TestCase):
    """ Tests for the Embargo check function. """

    @httpretty.activate
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

        httpretty.register_uri(
            httpretty.GET,
            self.site_configuration.build_lms_url('/api/embargo/v1/course_access/'),
            status=status_code,
            body=response,
            content_type='application/json'
        )

    @httpretty.activate
    def test_embargo_check_match(self):
        """ Verify the embargo check returns False. """
        embargo_response = {'access': False}
        self.mock_access_token_response()
        self.mock_embargo_response(json.dumps(embargo_response))
        response = self.site.siteconfiguration.embargo_api_client.course_access.get(**self.params)
        self.assertEqual(response, embargo_response)
