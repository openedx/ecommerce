

import mock

from ecommerce.core.exceptions import MissingRequestError
from ecommerce.core.url_utils import get_ecommerce_url, get_favicon_url, get_lms_url, get_logo_url
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

    @mock.patch('django.conf.settings.LOGO_URL', None)
    def test_get_logo_url_from_static_file(self):
        """
        If the django settings for the url are set to none, use the static asset
        """
        self.assertEqual(get_logo_url(), '/static/images/default-logo.png')

    def test_get_logo_url_from_settings(self):
        """
        Use the django settings value for the logo url if set
        """
        fake_logo_url = 'https://logo_url.org/logo.svg'
        with mock.patch('django.conf.settings.LOGO_URL', fake_logo_url):
            self.assertEqual(get_logo_url(), fake_logo_url)

    @mock.patch('django.conf.settings.FAVICON_URL', None)
    def test_get_favicon_url_from_static_file(self):
        """
        If the django settings for the favicon url are set to none, use the static asset
        """
        self.assertEqual(get_favicon_url(), '/static/images/favicon.ico')

    def test_get_favicon_url_from_settings(self):
        """
        Use the django settings value for the favicon url if set
        """
        fake_favicon_url = 'https://favicon_url.org/favicon.ico'
        with mock.patch('django.conf.settings.FAVICON_URL', fake_favicon_url):
            self.assertEqual(get_favicon_url(), fake_favicon_url)
