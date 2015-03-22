"""Tests of the service health endpoint."""
import json
import logging

import mock
from requests import Response
from requests.exceptions import RequestException
from rest_framework import status
from django.test import TestCase
from django.db import DatabaseError
from django.core.urlresolvers import reverse

from ecommerce.health.constants import Status


@mock.patch('requests.get')
class HealthTests(TestCase):
    """Tests of the health endpoint."""
    def setUp(self):
        self.fake_lms_response = Response()

        # Override all loggers, suppressing logging calls of severity CRITICAL and below
        logging.disable(logging.CRITICAL)

        # Remove logger override
        self.addCleanup(logging.disable, logging.NOTSET)

    def test_all_services_available(self, mock_lms_request):
        """Test that the endpoint reports when all services are healthy."""
        self.fake_lms_response.status_code = status.HTTP_200_OK
        mock_lms_request.return_value = self.fake_lms_response

        self._assert_health(status.HTTP_200_OK, Status.OK, Status.OK, Status.OK)

    @mock.patch('django.db.backends.BaseDatabaseWrapper.cursor', mock.Mock(side_effect=DatabaseError))
    def test_database_outage(self, mock_lms_request):
        """Test that the endpoint reports when the database is unavailable."""
        self.fake_lms_response.status_code = status.HTTP_200_OK
        mock_lms_request.return_value = self.fake_lms_response

        self._assert_health(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            Status.UNAVAILABLE,
            Status.UNAVAILABLE,
            Status.OK
        )

    def test_lms_outage(self, mock_lms_request):
        """Test that the endpoint reports when the LMS is experiencing difficulties."""
        self.fake_lms_response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        mock_lms_request.return_value = self.fake_lms_response

        self._assert_health(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            Status.UNAVAILABLE,
            Status.OK,
            Status.UNAVAILABLE
        )

    def test_lms_connection_failure(self, mock_lms_request):
        """Test that the endpoint reports when it cannot contact the LMS."""
        mock_lms_request.side_effect = RequestException

        self._assert_health(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            Status.UNAVAILABLE,
            Status.OK,
            Status.UNAVAILABLE
        )

    def _assert_health(self, status_code, overall_status, database_status, lms_status):
        """Verify that the response matches expectations."""
        response = self.client.get(reverse('health'))
        self.assertEqual(response.status_code, status_code)
        self.assertEqual(response['content-type'], 'application/json')

        expected_data = {
            'overall_status': overall_status,
            'detailed_status': {
                'database_status': database_status,
                'lms_status': lms_status
            }
        }
        self.assertDictEqual(json.loads(response.content), expected_data)
