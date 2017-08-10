import uuid

import httpretty

from ecommerce.programs.tests.mixins import ProgramTestMixin
from ecommerce.programs.utils import get_program
from ecommerce.tests.testcases import TestCase


class UtilTests(ProgramTestMixin, TestCase):
    def setUp(self):
        super(UtilTests, self).setUp()

    @httpretty.activate
    def test_get_program(self):
        """
        The method should return data from the Discovery Service API.
        Data should be cached for subsequent calls.
        """
        program_uuid = uuid.uuid4()
        data = self.mock_program_detail_endpoint(program_uuid, self.site.siteconfiguration.discovery_api_url)
        self.assertEqual(get_program(program_uuid, self.site.siteconfiguration), data)

        # The program data should be cached
        httpretty.disable()
        self.assertEqual(get_program(program_uuid, self.site.siteconfiguration), data)
