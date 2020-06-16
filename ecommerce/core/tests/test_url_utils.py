

import mock

from ecommerce.core.exceptions import MissingRequestError
from ecommerce.core.url_utils import get_ecommerce_url, get_lms_url
from ecommerce.tests.testcases import TestCase


class UrlUtilityTests(TestCase):
    @mock.patch('ecommerce.core.url_utils.get_current_request', mock.Mock(return_value=None))
    def test_get_ecommerce_url_with_no_current_request(self):
        with self.assertRaises(MissingRequestError):
            get_ecommerce_url()

    @mock.patch('ecommerce.core.url_utils.get_current_request', mock.Mock(return_value=None))
    def test_get_lms_url_with_no_current_request(self):
        with self.assertRaises(MissingRequestError):
            get_lms_url()
