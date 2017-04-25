import json

import ddt
import httpretty
import mock
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.test import override_settings
from edx_rest_api_client.auth import SuppliedJwtAuth
from requests.exceptions import ConnectionError

from ecommerce.core.models import BusinessClient, SiteConfiguration, User
from ecommerce.core.tests import toggle_switch
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.extensions.payment.tests.processors import AnotherDummyProcessor, DummyProcessor
from ecommerce.tests.factories import SiteConfigurationFactory
from ecommerce.tests.mixins import LmsApiMockMixin
from ecommerce.tests.testcases import TestCase

COURSE_CATALOG_API_URL = 'https://catalog.example.com/api/v1/'
ENTERPRISE_API_URL = 'https://enterprise.example.com/api/v1/'


def _make_site_config(payment_processors_str, site_id=1):
    site = Site.objects.get(id=site_id)

    return SiteConfiguration(
        site=site,
        payment_processors=payment_processors_str,
        from_email='sender@example.com'
    )


@ddt.ddt
class UserTests(CourseCatalogTestMixin, LmsApiMockMixin, TestCase):
    TEST_CONTEXT = {'foo': 'bar', 'baz': None}

    def test_access_token(self):
        user = self.create_user()
        self.assertIsNone(user.access_token)

        self.create_access_token(user)
        self.assertEqual(user.access_token, self.access_token)

    def test_tracking_context(self):
        """ Ensures that the tracking_context dictionary is written / read
        correctly by the User model. """
        user = self.create_user()
        self.assertIsNone(user.tracking_context)

        user.tracking_context = self.TEST_CONTEXT
        user.save()

        same_user = User.objects.get(id=user.id)
        self.assertEqual(same_user.tracking_context, self.TEST_CONTEXT)

    def test_get_full_name(self):
        """ Test that the user model concatenates first and last name if the full name is not set. """
        full_name = "George Costanza"
        user = self.create_user(full_name=full_name)
        self.assertEquals(user.get_full_name(), full_name)

        first_name = "Jerry"
        last_name = "Seinfeld"
        user = self.create_user(full_name=None, first_name=first_name, last_name=last_name)
        expected = "{first_name} {last_name}".format(first_name=first_name, last_name=last_name)
        self.assertEquals(user.get_full_name(), expected)

        user = self.create_user(full_name=full_name, first_name=first_name, last_name=last_name)
        self.assertEquals(user.get_full_name(), full_name)

    @httpretty.activate
    def test_user_details(self):
        """ Verify user details are returned. """
        user = self.create_user()
        user_details = {'is_active': True}
        self.mock_account_api(self.request, user.username, data=user_details)
        self.mock_access_token_response()
        self.assertDictEqual(user.account_details(self.request), user_details)

    @httpretty.activate
    def test_user_details_uses_jwt(self):
        """Verify user_details uses jwt from site configuration to call EdxRestApiClient."""
        user = self.create_user()
        user_details = {'is_active': True}
        self.mock_account_api(self.request, user.username, data=user_details)
        token = self.mock_access_token_response()

        user.account_details(self.request)
        last_request = httpretty.last_request()

        # Verify the headers passed to the API were correct.
        expected = {'Authorization': 'JWT {}'.format(token), }
        self.assertDictContainsSubset(expected, last_request.headers)

    def test_no_user_details(self):
        """ Verify False is returned when there is a connection error. """
        user = self.create_user()
        with self.assertRaises(ConnectionError):
            self.assertFalse(user.account_details(self.request))

    def prepare_credit_eligibility_info(self, eligible=True):
        """ Helper method for setting up LMS eligibility info. """
        user = self.create_user()
        course_key = 'a/b/c'
        self.mock_eligibility_api(self.request, user, course_key, eligible=eligible)
        return user, course_key

    @httpretty.activate
    def test_user_is_eligible(self):
        """ Verify the method returns eligibility information. """
        user, course_key = self.prepare_credit_eligibility_info()
        self.assertEqual(user.is_eligible_for_credit(course_key)[0]['username'], user.username)
        self.assertEqual(user.is_eligible_for_credit(course_key)[0]['course_key'], course_key)

    @httpretty.activate
    def test_user_is_not_eligible(self):
        """ Verify method returns false (empty list) if user is not eligible. """
        user, course_key = self.prepare_credit_eligibility_info(eligible=False)
        self.assertFalse(user.is_eligible_for_credit(course_key))

    @httpretty.activate
    @ddt.data(
        (200, True),
        (200, False),
        (404, False)
    )
    @ddt.unpack
    def test_user_verification_status(self, status_code, is_verified):
        """ Verify the method returns correct response. """
        user = self.create_user()
        self.mock_verification_status_api(self.site, user, status=status_code, is_verified=is_verified)
        self.assertEqual(user.is_verified(self.site), is_verified)

    def test_user_verification_connection_error(self):
        """ Verify verification status exception is raised for connection issues. """
        user = self.create_user()
        self.assertFalse(user.is_verified(self.site))

    @httpretty.activate
    def test_user_verification_status_cache(self):
        """ Verify the user verification status values are cached. """
        user = self.create_user()
        self.mock_verification_status_api(self.site, user)
        self.assertTrue(user.is_verified(self.site))

        httpretty.disable()
        self.assertTrue(user.is_verified(self.site))

    @httpretty.activate
    def test_user_verification_status_not_cached(self):
        """ Verify the user verification status values is not cached when user is not verified. """
        user = self.create_user()
        self.mock_verification_status_api(self.site, user, is_verified=False)
        self.assertFalse(user.is_verified(self.site))

        httpretty.disable()
        self.assertFalse(user.is_verified(self.site))

    @httpretty.activate
    def test_deactivation(self):
        """Verify the deactivation endpoint is called for the user."""
        user = self.create_user()
        expected_response = {'user_deactivated': True}
        self.mock_deactivation_api(self.request, user.username, response=json.dumps(expected_response))
        self.mock_access_token_response()

        self.assertEqual(user.deactivate_account(self.request.site.siteconfiguration), expected_response)

    def test_deactivation_exception_handling(self):
        """Verify an error is logged if an exception happens."""

        def callback(*args):  # pylint: disable=unused-argument
            raise ConnectionError

        user = self.create_user()
        self.mock_deactivation_api(self.request, user.username, response=callback)

        with self.assertRaises(ConnectionError):
            with mock.patch('ecommerce.core.models.log.exception') as mock_logger:
                user.deactivate_account(self.request.site.siteconfiguration)
                self.assertTrue(mock_logger.called)


class BusinessClientTests(TestCase):
    def test_str(self):
        client = BusinessClient.objects.create(name='TestClient')
        self.assertEquals(str(client), 'TestClient')

    def test_creating_without_client_name_raises_exception(self):
        with self.assertRaises(ValidationError):
            BusinessClient.objects.create()


@ddt.ddt
class SiteConfigurationTests(TestCase):
    @ddt.data(
        ('paypal', {'paypal'}),
        ('paypal ', {'paypal'}),
        ('paypal,cybersource', {'paypal', 'cybersource'}),
        ('paypal, cybersource', {'paypal', 'cybersource'}),
        ('paypal,cybersource,something_else', {'paypal', 'cybersource', 'something_else'}),
        ('paypal , cybersource , something_else', {'paypal', 'cybersource', 'something_else'}),
    )
    @ddt.unpack
    def test_payment_processor_field_parsing(self, payment_processors_str, expected_result):
        """
        Tests that comma-separated payment processor string is correctly converted to a set of payment processor names
        :param str payment_processors_str: comma-separated string of processor names (potentially with spaces)
        :param set[str] expected_result: expected payment_processors_set result
        """
        site_config = _make_site_config(payment_processors_str)
        self.assertEqual(site_config.payment_processors_set, expected_result)

    @staticmethod
    def _enable_processor_switches(processors):
        for processor in processors:
            toggle_switch(settings.PAYMENT_PROCESSOR_SWITCH_PREFIX + processor.NAME, True)

    @override_settings(PAYMENT_PROCESSORS=[
        'ecommerce.extensions.payment.tests.processors.DummyProcessor',
        'ecommerce.extensions.payment.tests.processors.AnotherDummyProcessor',
    ])
    @ddt.data(
        ([], []),
        ([DummyProcessor], [DummyProcessor]),
        ([DummyProcessor, AnotherDummyProcessor], [DummyProcessor, AnotherDummyProcessor]),
    )
    @ddt.unpack
    def test_get_payment_processors(self, processors, expected_result):
        """ Tests that get_payment_processors returs correct payment processor classes """
        self._enable_processor_switches(processors)
        site_config = _make_site_config(",".join(proc.NAME for proc in processors))

        result = site_config.get_payment_processors()
        self.assertEqual(result, expected_result)

    @override_settings(PAYMENT_PROCESSORS=[
        'ecommerce.extensions.payment.tests.processors.DummyProcessor',
    ])
    def test_get_payment_processors_logs_warning_for_unknown_processors(self):
        """ Tests that get_payment_processors logs warnings if unknown payment processor codes are seen """
        processors = [DummyProcessor, AnotherDummyProcessor]
        site_config = _make_site_config(",".join(proc.NAME for proc in processors))
        with mock.patch("ecommerce.core.models.log") as patched_log:
            site_config.get_payment_processors()
            patched_log.warning.assert_called_once_with(
                'Unknown payment processors [%s] are configured for site %s',
                AnotherDummyProcessor.NAME,
                site_config.site.id
            )

    @override_settings(PAYMENT_PROCESSORS=[
        'ecommerce.extensions.payment.tests.processors.DummyProcessor',
        'ecommerce.extensions.payment.tests.processors.AnotherDummyProcessor',
    ])
    @ddt.data(
        [DummyProcessor],
        [DummyProcessor, AnotherDummyProcessor]
    )
    def test_get_payment_processors_switch_disabled(self, processors):
        """ Tests that get_payment_processors respects waffle switches """
        expected_result = []
        site_config = _make_site_config(",".join(proc.NAME for proc in processors))

        result = site_config.get_payment_processors()
        self.assertEqual(result, expected_result)

    def test_get_client_side_payment_processor(self):
        """ Verify the method returns the client-side payment processor. """
        PROCESSOR_NAME = 'cybersource'
        site_config = _make_site_config(PROCESSOR_NAME)

        site_config.client_side_payment_processor = None
        self.assertIsNone(site_config.get_client_side_payment_processor_class())

        site_config.client_side_payment_processor = PROCESSOR_NAME
        self.assertEqual(site_config.get_client_side_payment_processor_class().NAME, PROCESSOR_NAME)

    def test_get_from_email(self):
        """
        Validate SiteConfiguration.get_from_email() along with whether, or not,
        the base from email address is actually changed when a site-specific value is specified.
        """
        site_config = SiteConfigurationFactory(from_email='')
        self.assertEqual(site_config.get_from_email(), settings.OSCAR_FROM_EMAIL)

        expected_from_email = 'expected@email.com'
        site_config = SiteConfigurationFactory(from_email=expected_from_email)
        self.assertEqual(site_config.get_from_email(), expected_from_email)

    @httpretty.activate
    def test_access_token(self):
        """ Verify the property retrieves, and caches, an access token from the OAuth 2.0 provider. """
        token = self.mock_access_token_response()
        self.assertEqual(self.site.siteconfiguration.access_token, token)
        self.assertTrue(httpretty.has_request())

        # Verify the value is cached
        httpretty.disable()
        self.assertEqual(self.site.siteconfiguration.access_token, token)

    @httpretty.activate
    @override_settings(COURSE_CATALOG_API_URL=COURSE_CATALOG_API_URL)
    def test_course_catalog_api_client(self):
        """ Verify the property returns a Course Catalog API client. """
        token = self.mock_access_token_response()
        client = self.site.siteconfiguration.course_catalog_api_client
        client_store = client._store  # pylint: disable=protected-access
        client_auth = client_store['session'].auth

        self.assertEqual(client_store['base_url'], COURSE_CATALOG_API_URL)
        self.assertIsInstance(client_auth, SuppliedJwtAuth)
        self.assertEqual(client_auth.token, token)

    @httpretty.activate
    @override_settings(ENTERPRISE_API_URL=ENTERPRISE_API_URL)
    def test_enterprise_api_client(self):
        """
        Verify the property "enterprise_api_client" returns a Slumber-based
        REST API client for enterprise service API.
        """
        token = self.mock_access_token_response()
        client = self.site.siteconfiguration.enterprise_api_client
        client_store = client._store  # pylint: disable=protected-access
        client_auth = client_store['session'].auth

        self.assertEqual(client_store['base_url'], ENTERPRISE_API_URL)
        self.assertIsInstance(client_auth, SuppliedJwtAuth)
        self.assertEqual(client_auth.token, token)
