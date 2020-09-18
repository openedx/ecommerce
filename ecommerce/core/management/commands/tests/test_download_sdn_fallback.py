"""
Tests for Django management command to download csv for SDN fallback.
"""
import requests
import responses
from django.core.management import call_command
from mock import patch
from testfixtures import LogCapture, StringComparison

from ecommerce.tests.testcases import TestCase


class TestDownloadSndFallbackCommand(TestCase):

    LOGGER_NAME = 'ecommerce.core.management.commands.populate_sdn_fallback_data_and_metadata'

    def setUp(self):
        class TestResponse:
            def __init__(self, **kwargs):
                self.__dict__ = kwargs

        #  mock response for csv download: just one row of the csv
        self.test_response = TestResponse(**{
            'content': bytes('_id,source,entity_number,type,programs,name,title,addresses,federal_register_notice,start_date,end_date,standard_order,license_requirement,license_policy,call_sign,vessel_type,gross_tonnage,gross_registered_tonnage,vessel_flag,vessel_owner,remarks,source_list_url,alt_names,citizenships,dates_of_birth,nationalities,places_of_birth,source_information_url,ids\ne5a9eff64cec4a74ed5e9e93c2d851dc2d9132d2,Denied Persons List (DPL) - Bureau of Industry and Security,,,, MICKEY MOUSE,,"123 S. TEST DRIVE, SCOTTSDALE, AZ, 85251",82 F.R. 48792 10/01/2017,2017-10-18,2020-10-15,Y,,,,,,,,,FR NOTICE ADDED,http://bit.ly/1Qi5heF,,,,,,http://bit.ly/1iwxiF0', 'utf-8'),  # pylint: disable=line-too-long
            'status_code': 200,
        })
        self.test_response_500 = TestResponse(**{
            'status_code': 500,
        })

    @patch('requests.Session.get')
    def test_handle_pass(self, mock_response):
        """ Test using mock response from setup, using threshold it will clear"""

        mock_response.return_value = self.test_response

        with LogCapture(self.LOGGER_NAME) as log:
            call_command('populate_sdn_fallback_data_and_metadata', '--threshold=0.0001')

            log.check(
                (
                    self.LOGGER_NAME,
                    'INFO',
                    StringComparison(
                        r'(?s)SDNFallback: IMPORT SUCCESS: Imported SDN CSV\. Metadata id.*')
                ),
                (
                    self.LOGGER_NAME,
                    'INFO',
                    "SDNFallback: DOWNLOAD SUCCESS: Successfully downloaded the SDN CSV."
                )
            )

    @patch('requests.Session.get')
    def test_handle_fail_size(self, mock_response):
        """ Test using mock response from setup, using threshold it will NOT clear"""

        mock_response.return_value = self.test_response

        with LogCapture(self.LOGGER_NAME) as log:
            with self.assertRaises(Exception) as e:
                call_command('populate_sdn_fallback_data_and_metadata', '--threshold=1')

            log.check(
                (
                    self.LOGGER_NAME,
                    'WARNING',
                    "SDNFallback: DOWNLOAD FAILURE: file too small! (0.000642 MB vs threshold of 1.0 MB)"
                )
            )
        self.assertEqual('CSV file download did not meet threshold given', str(e.exception))

    @patch('requests.Session.get')
    def test_handle_500_response(self, mock_response):
        """ Test using url for 500 error"""
        mock_response.return_value = self.test_response_500
        with LogCapture(self.LOGGER_NAME) as log:
            with self.assertRaises(Exception) as e:
                call_command('populate_sdn_fallback_data_and_metadata', '--threshold=1')

            log.check(
                (
                    self.LOGGER_NAME,
                    'WARNING',
                    "SDNFallback: DOWNLOAD FAILURE: Status code was: [500]"
                )
            )
        self.assertEqual("('CSV download url got an unsuccessful response code: ', 500)", str(e.exception))


class TestDownloadSndFallbackCommandExceptions(TestCase):
    LOGGER_NAME = 'ecommerce.core.management.commands.populate_sdn_fallback_data_and_metadata'
    URL = 'http://api.trade.gov/static/consolidated_screening_list/consolidated.csv'
    ERROR_MESSAGE = 'some foo error'

    @responses.activate
    def test_general_exception(self):
        responses.add(responses.GET, self.URL, body=Exception(self.ERROR_MESSAGE))

        with LogCapture(self.LOGGER_NAME) as log:
            with self.assertRaises(Exception) as e:
                call_command('populate_sdn_fallback_data_and_metadata')

            log.check(
                (
                    self.LOGGER_NAME,
                    'WARNING',
                    "SDNFallback: DOWNLOAD FAILURE: Exception occurred: [%s]" % self.ERROR_MESSAGE
                )
            )

        self.assertEqual(self.ERROR_MESSAGE, str(e.exception))

    @responses.activate
    def test_timeout_exception(self):
        responses.add(responses.GET, self.URL, body=requests.exceptions.ConnectTimeout(self.ERROR_MESSAGE))

        with LogCapture(self.LOGGER_NAME) as log:
            with self.assertRaises(Exception) as e:
                call_command('populate_sdn_fallback_data_and_metadata')

            log.check(
                (
                    self.LOGGER_NAME,
                    'WARNING',
                    "SDNFallback: DOWNLOAD FAILURE: Timeout occurred trying to download SDN csv. Timeout threshold (in seconds): 5"  # pylint: disable=line-too-long
                )
            )

        self.assertEqual(self.ERROR_MESSAGE, str(e.exception))
