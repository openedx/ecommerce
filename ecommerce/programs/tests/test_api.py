

import uuid

import httpretty
from requests import ConnectionError as ReqConnectionError

from ecommerce.programs.api import ProgramsApiClient
from ecommerce.programs.tests.mixins import ProgramTestMixin
from ecommerce.tests.testcases import TestCase


class ProgramsApiClientTests(ProgramTestMixin, TestCase):
    def setUp(self):
        super(ProgramsApiClientTests, self).setUp()

        httpretty.enable()
        self.mock_access_token_response()
        self.client = ProgramsApiClient(self.site.siteconfiguration.discovery_api_client, self.site.domain)

    def tearDown(self):
        super(ProgramsApiClientTests, self).tearDown()
        httpretty.disable()
        httpretty.reset()

    def test_get_program(self):
        """ The method should return data from the Programs API. Data should be cached for subsequent calls. """
        program_uuid = uuid.uuid4()
        data = self.mock_program_detail_endpoint(program_uuid, self.site_configuration.discovery_api_url)
        self.assertEqual(self.client.get_program(program_uuid), data)

        # Subsequent calls should pull from the cache
        httpretty.disable()
        self.assertEqual(self.client.get_program(program_uuid), data)

        # Calls from different domains should not pull from cache
        self.client.site_domain = 'different-domain'
        with self.assertRaises(ReqConnectionError):
            self.client.get_program(program_uuid)
