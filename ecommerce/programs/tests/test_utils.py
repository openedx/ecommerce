

import uuid

import ddt
import httpretty
import mock
from requests.exceptions import ConnectionError as ReqConnectionError
from requests.exceptions import Timeout
from slumber.exceptions import HttpNotFoundError, SlumberBaseException
from testfixtures import LogCapture

from ecommerce.programs.api import ProgramsApiClient
from ecommerce.programs.tests.mixins import ProgramTestMixin
from ecommerce.programs.utils import get_program
from ecommerce.tests.testcases import TestCase

LOGGER_NAME = 'ecommerce.programs.utils'


@ddt.ddt
class UtilTests(ProgramTestMixin, TestCase):
    def setUp(self):
        super(UtilTests, self).setUp()
        self.program_uuid = uuid.uuid4()
        self.discovery_api_url = self.site.siteconfiguration.discovery_api_url

    @httpretty.activate
    def test_get_program(self):
        """
        The method should return data from the Discovery Service API.
        Data should be cached for subsequent calls.
        """
        data = self.mock_program_detail_endpoint(self.program_uuid, self.discovery_api_url)
        self.assertEqual(get_program(self.program_uuid, self.site.siteconfiguration), data)

        # The program data should be cached
        httpretty.disable()
        self.assertEqual(get_program(self.program_uuid, self.site.siteconfiguration), data)

    @httpretty.activate
    @ddt.data(ReqConnectionError, SlumberBaseException, Timeout)
    def test_get_program_failure(self, exc):  # pylint: disable=unused-argument
        """
        The method should log errors in retrieving program data
        """
        self.mock_program_detail_endpoint(self.program_uuid, self.discovery_api_url, empty=True)
        with mock.patch.object(ProgramsApiClient, 'get_program', side_effect=exc):
            with LogCapture(LOGGER_NAME) as logger:
                response = get_program(self.program_uuid, self.site.siteconfiguration)
                self.assertIsNone(response)
                msg = 'Failed to retrieve program details for {}'.format(self.program_uuid)
                logger.check((LOGGER_NAME, 'DEBUG', msg))

    @httpretty.activate
    def test_get_program_not_found(self):  # pylint: disable=unused-argument
        """
        The method should log not found errors for program data
        """
        self.mock_program_detail_endpoint(self.program_uuid, self.discovery_api_url, empty=True)
        with mock.patch.object(ProgramsApiClient, 'get_program', side_effect=HttpNotFoundError):
            with LogCapture(LOGGER_NAME) as logger:
                response = get_program(self.program_uuid, self.site.siteconfiguration)
                self.assertIsNone(response)
                msg = 'No program data found for {}'.format(self.program_uuid)
                logger.check((LOGGER_NAME, 'DEBUG', msg))
