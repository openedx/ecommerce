

import json

import ddt
import mock
import responses
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.test import override_settings
from edx_rest_api_client.client import OAuthAPIClient
from requests.exceptions import ConnectionError as ReqConnectionError
from social_django.models import UserSocialAuth
from testfixtures import LogCapture
from waffle.testutils import override_flag

from ecommerce.core.models import (
    BusinessClient,
    EcommerceFeatureRole,
    EcommerceFeatureRoleAssignment,
    SiteConfiguration,
    User
)
from ecommerce.core.tests import toggle_switch
from ecommerce.extensions.basket.constants import ENABLE_STRIPE_PAYMENT_PROCESSOR
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.extensions.payment.tests.processors import AnotherDummyProcessor, DummyProcessor
from ecommerce.tests.factories import SiteConfigurationFactory
from ecommerce.tests.mixins import LmsApiMockMixin
from ecommerce.tests.testcases import TestCase

ENTERPRISE_API_URL = 'https://enterprise.example.com/api/v1/'


def _make_site_config(payment_processors_str, site_id=1):
    site = Site.objects.get(id=site_id)

    return SiteConfiguration(
        site=site,
        payment_processors=payment_processors_str,
        from_email='sender@example.com'
    )


@ddt.ddt
class UserTests(DiscoveryTestMixin, LmsApiMockMixin, TestCase):
    TEST_CONTEXT = {'foo': 'bar', 'baz': None, 'lms_user_id': 'test-context-user-id'}
    LMS_USER_ID = 500
    LOGGER_NAME = 'ecommerce.core.models'

    def setUp(self):
        super().setUp()
        self.mock_access_token_response()
        responses.start()

    def tearDown(self):
        super().tearDown()
        responses.stop()
        responses.reset()

    def test_access_token(self):
        """ Ensures the access token can be pulled from the ecommerce user. """
        user = self.create_user()
        self.assertIsNone(user.access_token)

        self.create_access_token(user)

        same_user = User.objects.get(id=user.id)
        self.assertEqual(same_user.social_auth.count(), 1)
        self.assertEqual(same_user.access_token, self.access_token)

    def test_multiple_access_tokens(self):
        """ Ensures the correct access token is pulled from the ecommerce user when multiple social auth entries
        exist for that user. """
        user = self.create_user()
        self.assertIsNone(user.access_token)

        lms_user_id = 6181
        expected_access_token = 'access_token_3'
        UserSocialAuth.objects.create(user=user, provider='edx-oidc', uid='older_6181',
                                      extra_data={'user_id': lms_user_id, 'access_token': 'access_token_1'})
        UserSocialAuth.objects.create(user=user, provider='edx-oauth2', uid='older_6181',
                                      extra_data={'user_id': lms_user_id, 'access_token': 'access_token_2'})
        UserSocialAuth.objects.create(user=user, provider='edx-oauth2',
                                      extra_data={'user_id': lms_user_id, 'access_token': expected_access_token})

        same_user = User.objects.get(id=user.id)
        self.assertEqual(same_user.social_auth.count(), 3)
        self.assertEqual(same_user.access_token, expected_access_token)

    def test_lms_user_id_with_metric(self):
        """ Ensures the lms_user_id can be pulled from the ecommerce user. """
        user = self.create_user()

        user.lms_user_id = self.LMS_USER_ID
        user.save()

        same_user = User.objects.get(id=user.id)
        user_id = same_user.lms_user_id_with_metric()
        self.assertEqual(user_id, self.LMS_USER_ID)

    def test_missing_lms_user_id_with_metric(self):
        """ Ensures a missing lms_user_id is handled by lms_user_id_with_metric(). """
        user = self.create_user(lms_user_id=None)
        expected_logs = [
            (
                self.LOGGER_NAME,
                'WARNING',
                'Could not find lms_user_id with metric for user {} for None.'.format(user.id)
            ),
        ]

        with LogCapture(self.LOGGER_NAME) as log:
            same_user = User.objects.get(id=user.id)
            user_id = same_user.lms_user_id_with_metric()
            log.check_present(*expected_logs)
            self.assertIsNone(user_id)

    def test_tracking_context(self):
        """ Ensures that the tracking_context dictionary is written / read
        correctly by the User model. """
        user = self.create_user()
        self.assertIsNone(user.tracking_context)

        user.tracking_context = self.TEST_CONTEXT
        user.save()

        same_user = User.objects.get(id=user.id)
        self.assertEqual(same_user.tracking_context, self.TEST_CONTEXT)

    def test_lms_user_id(self):
        """ Ensures that the LMS user id is written / read correctly by the User model. """
        user = self.create_user(lms_user_id=None)
        self.assertIsNone(user.lms_user_id)

        user.lms_user_id = self.LMS_USER_ID
        user.save()

        same_user = User.objects.get(id=user.id)
        self.assertEqual(same_user.lms_user_id, self.LMS_USER_ID)

    def test_get_full_name(self):
        """ Test that the user model concatenates first and last name if the full name is not set. """
        full_name = "George Costanza"
        user = self.create_user(full_name=full_name)
        self.assertEqual(user.get_full_name(), full_name)

        first_name = "Jerry"
        last_name = "Seinfeld"
        user = self.create_user(full_name=None, first_name=first_name, last_name=last_name)
        expected = "{first_name} {last_name}".format(first_name=first_name, last_name=last_name)
        self.assertEqual(user.get_full_name(), expected)

        user = self.create_user(full_name=full_name, first_name=first_name, last_name=last_name)
        self.assertEqual(user.get_full_name(), full_name)

    def test_user_details(self):
        """ Verify user details are returned. """
        user = self.create_user()
        user_details = {'is_active': True}
        self.mock_account_api(self.request, user.username, data=user_details)
        self.mock_access_token_response()
        self.assertDictEqual(user.account_details(self.request), user_details)

    def test_user_details_uses_jwt(self):
        """
        Verify user_details uses jwt from site configuration when using the OAuthAPIClient.
        """
        user = self.create_user()
        user_details = {'is_active': True}
        self.mock_account_api(self.request, user.username, data=user_details)
        token = self.mock_access_token_response()

        user.account_details(self.request)
        last_request = responses.calls[-1].request

        # Verify the headers passed to the API were correct.
        expected = {'Authorization': 'JWT {}'.format(token), }
        self.assertDictContainsSubset(expected, last_request.headers)

    def test_no_user_details(self):
        """ Verify False is returned when there is a connection error. """
        user = self.create_user()
        with self.assertRaises(ReqConnectionError):
            self.assertFalse(user.account_details(self.request))

    def prepare_credit_eligibility_info(self, eligible=True):
        """ Helper method for setting up LMS eligibility info. """
        user = self.create_user()
        course_key = 'a/b/c'
        self.mock_eligibility_api(self.request, user, course_key, eligible=eligible)
        return user, course_key

    def test_user_is_eligible(self):
        """ Verify the method returns eligibility information. """
        site_config = self.request.site.siteconfiguration
        user, course_key = self.prepare_credit_eligibility_info()
        self.assertEqual(user.is_eligible_for_credit(course_key, site_config)[0]['username'], user.username)
        self.assertEqual(user.is_eligible_for_credit(course_key, site_config)[0]['course_key'], course_key)

    def test_user_is_not_eligible(self):
        """ Verify method returns false (empty list) if user is not eligible. """
        site_config = self.request.site.siteconfiguration
        user, course_key = self.prepare_credit_eligibility_info(eligible=False)
        self.assertFalse(user.is_eligible_for_credit(course_key, site_config))

    def test_deactivation(self):
        """Verify the deactivation endpoint is called for the user."""
        user = self.create_user()
        expected_response = {'user_deactivated': True}
        self.mock_access_token_response()
        self.mock_deactivation_api(self.request, user.username, response=json.dumps(expected_response))

        self.assertEqual(user.deactivate_account(self.request.site.siteconfiguration), expected_response)

    def test_deactivation_exception_handling(self):
        """
        Verify an error is logged if an exception happens.
        """
        user = self.create_user()
        self.mock_deactivation_api(self.request, user.username, response=ReqConnectionError)

        with self.assertRaises(ReqConnectionError):
            with mock.patch('ecommerce.core.models.log.exception') as mock_logger:
                user.deactivate_account(self.request.site.siteconfiguration)
                self.assertTrue(mock_logger.called)


class BusinessClientTests(TestCase):
    def test_str(self):
        client = BusinessClient.objects.create(name='TestClient')
        self.assertEqual(str(client), 'TestClient')

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

    @ddt.data(
        ('paypal', None),
        ('paypal ', None),
        ('paypal,cybersource', None),
        ('paypal, cybersource', None),
        ('paypal,cybersource,something_else', ValidationError),
        ('paypal , cybersource , something_else', ValidationError),
        (' ', ValidationError),
    )
    @ddt.unpack
    def test_clean_processors(self, payment_processors_str, expected_exception):
        site_config = _make_site_config(payment_processors_str)

        if expected_exception is None:
            site_config._clean_payment_processors()  # pylint: disable=protected-access
        else:
            with self.assertRaises(expected_exception):
                site_config._clean_payment_processors()  # pylint: disable=protected-access

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
        """ Tests that get_payment_processors returns correct payment processor classes """
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
        processor_name = 'cybersource'
        site_config = _make_site_config(processor_name)

        site_config.client_side_payment_processor = None
        self.assertIsNone(site_config.get_client_side_payment_processor_class(request=None))

        site_config.client_side_payment_processor = processor_name
        self.assertEqual(site_config.get_client_side_payment_processor_class(request=None).NAME, processor_name)

    @override_flag(ENABLE_STRIPE_PAYMENT_PROCESSOR, active=True)
    def test_get_client_side_payment_processor_waffle_enabled(self):
        """ Verify that Stripe is always returned when waffle flag is on. """
        processor_name = 'cybersource,stripe'
        site_config = _make_site_config(processor_name)

        site_config.client_side_payment_processor = None
        self.assertIsNone(site_config.get_client_side_payment_processor_class(request=None))

        site_config.client_side_payment_processor = 'cybersource'
        self.assertEqual(site_config.get_client_side_payment_processor_class(request=None).NAME, 'stripe')

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

    @responses.activate
    def test_oauth_api_client(self):
        """
        Verify the property retrieves, and caches, an access token from the OAuth 2.0 provider.
        """
        token = self.mock_access_token_response()
        site_config = SiteConfigurationFactory()
        client = site_config.oauth_api_client
        self.assertEqual(type(client), OAuthAPIClient)
        self.assertEqual(client.get_jwt_access_token(), token)
        self.assertEqual(len(responses.calls), 1)


class EcommerceFeatureRoleTests(TestCase):
    def test_str(self):
        role = EcommerceFeatureRole.objects.create(name='TestRole')
        self.assertEqual(str(role), '<EcommerceFeatureRole TestRole>')

    def test_repr(self):
        role = EcommerceFeatureRole.objects.create(name='TestRole')
        self.assertEqual(repr(role), '<EcommerceFeatureRole TestRole>')


class EcommerceFeatureRoleAssignmentTests(TestCase):
    def test_str(self):
        role = EcommerceFeatureRole.objects.create(name='TestRole')
        user = self.create_user()
        role_assignment = EcommerceFeatureRoleAssignment.objects.create(role=role, user=user)
        self.assertEqual(
            str(role_assignment),
            '<EcommerceFeatureRoleAssignment for User {user} assigned to role {role}>'.format(
                user=user.id, role=role.name
            )
        )

    def test_repr(self):
        role = EcommerceFeatureRole.objects.create(name='TestRole')
        user = self.create_user()
        role_assignment = EcommerceFeatureRoleAssignment.objects.create(role=role, user=user)
        self.assertEqual(
            repr(role_assignment),
            '<EcommerceFeatureRoleAssignment for User {user} assigned to role {role}>'.format(
                user=user.id, role=role.name
            )
        )
