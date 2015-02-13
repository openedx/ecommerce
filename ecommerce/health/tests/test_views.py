"""Tests of the service health endpoint."""
import json
import logging

import mock
from requests import Response
from rest_framework import status
from django.test import TestCase
from django.db import DatabaseError
from django.core.urlresolvers import reverse

from health.views import OK, UNAVAILABLE


@mock.patch('requests.get')
class HealthViewTests(TestCase):
    def setUp(self):
        self.fake_lms_response = Response()

        # Override all loggers, suppressing logging calls of severity CRITICAL and below
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        # Remove logger override
        logging.disable(logging.NOTSET)

    def test_healthy(self, mock_lms_request):
        self.fake_lms_response.status_code = status.HTTP_200_OK
        mock_lms_request.return_value = self.fake_lms_response

        response = self.client.get(reverse('health'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['content-type'], 'application/json')

        expected_data = {
            'overall_status': OK,
            'detailed_status': {
                'database_status': OK,
                'lms_status': OK
            }
        }
        self.assertDictEqual(json.loads(response.content), expected_data)

    @mock.patch('django.db.backends.BaseDatabaseWrapper.cursor', mock.Mock(side_effect=DatabaseError))
    def test_database_outage(self, mock_lms_request):
        self.fake_lms_response.status_code = status.HTTP_200_OK
        mock_lms_request.return_value = self.fake_lms_response

        response = self.client.get(reverse('health'))
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response['content-type'], 'application/json')

        expected_data = {
            'overall_status': UNAVAILABLE,
            'detailed_status': {
                'database_status': UNAVAILABLE,
                'lms_status': OK
            }
        }
        self.assertDictEqual(json.loads(response.content), expected_data)

    def test_health_lms_outage(self, mock_lms_request):
        self.fake_lms_response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        mock_lms_request.return_value = self.fake_lms_response

        response = self.client.get(reverse('health'))
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response['content-type'], 'application/json')

        expected_data = {
            'overall_status': UNAVAILABLE,
            'detailed_status': {
                'database_status': OK,
                'lms_status': UNAVAILABLE
            }
        }
        self.assertDictEqual(json.loads(response.content), expected_data)
