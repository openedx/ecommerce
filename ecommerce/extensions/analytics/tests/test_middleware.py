

from django.test.client import RequestFactory
from social_django.models import UserSocialAuth
from testfixtures import LogCapture
from waffle.testutils import override_switch

from ecommerce.core.constants import ALLOW_MISSING_LMS_USER_ID
from ecommerce.core.exceptions import MissingLmsUserIdException
from ecommerce.core.models import User
from ecommerce.extensions.analytics import middleware
from ecommerce.tests.testcases import TestCase


class TrackingMiddlewareTests(TestCase):
    """ Test for TrackingMiddleware. """
    TEST_CONTEXT = {'foo': 'bar', 'baz': None, 'lms_user_id': 12345}
    MODEL_LOGGER_NAME = 'ecommerce.core.models'

    def setUp(self):
        super(TrackingMiddlewareTests, self).setUp()
        self.middleware = middleware.TrackingMiddleware()
        self.request_factory = RequestFactory()
        self.user = self.create_user()

    def _process_view(self, user):
        request = self.request_factory.get('/')
        request.user = user
        self.middleware.process_view(request, None, None, None)

    def _assert_ga_client_id(self, ga_client_id):
        self.request_factory.cookies['_ga'] = 'GA1.2.{}'.format(ga_client_id)
        self._process_view(self.user)
        expected_client_id = self.user.tracking_context.get('ga_client_id')
        self.assertEqual(ga_client_id, expected_client_id)

    def test_save_ga_client_id(self):
        """ Test that middleware save/update GA client id in user tracking context. """
        self.assertIsNone(self.user.tracking_context)
        self._assert_ga_client_id('test-client-id')

        updated_client_id = 'updated-client-id'
        self.assertNotEqual(updated_client_id, self.user.tracking_context.get('ga_client_id'))
        self._assert_ga_client_id(updated_client_id)

    def test_social_auth_lms_user_id(self):
        """ Test that middleware saves the LMS user_id from the social auth. """
        user = self.create_user(lms_user_id=None)
        user.tracking_context = self.TEST_CONTEXT
        user.save()

        lms_user_id = 67890
        UserSocialAuth.objects.create(user=user, provider='edx-oauth2', extra_data={'user_id': lms_user_id})

        same_user = User.objects.get(id=user.id)
        self.assertIsNone(same_user.lms_user_id)

        self._process_view(same_user)
        same_user = User.objects.get(id=user.id)
        self.assertEqual(same_user.lms_user_id, lms_user_id)

    def test_social_auth_multiple_entries_lms_user_id(self):
        """ Test that middleware saves the LMS user_id from the social auth, when multiple social auth entries
        exist for that user. """
        user = self.create_user(lms_user_id=None)
        user.tracking_context = self.TEST_CONTEXT
        user.save()

        lms_user_id = 91827
        UserSocialAuth.objects.create(user=user, provider='edx-oidc', uid='older_45', extra_data={'user_id': 123})
        UserSocialAuth.objects.create(user=user, provider='edx-oidc', extra_data={'user_id': 456})
        social_auth = UserSocialAuth.objects.create(user=user, provider='edx-oauth2',
                                                    extra_data={'user_id': lms_user_id})
        UserSocialAuth.objects.create(user=user, provider='edx-oauth2', uid='newer_45')

        same_user = User.objects.get(id=user.id)
        self.assertIsNone(same_user.lms_user_id)
        self.assertEqual(same_user.social_auth.count(), 4)

        expected = [
            (
                self.MODEL_LOGGER_NAME,
                'INFO',
                'Saving lms_user_id from social auth with id {} for user {}. Called from middleware with request '
                'path: /, referrer: None'.format(social_auth.id, user.id)
            ),
        ]
        same_user = User.objects.get(id=user.id)
        with LogCapture(self.MODEL_LOGGER_NAME) as log:
            self._process_view(same_user)
            log.check_present(*expected)

        same_user = User.objects.get(id=user.id)
        self.assertEqual(same_user.lms_user_id, lms_user_id)

    def test_does_not_overwrite_lms_user_id(self):
        """ Test that middleware does not overwrite an existing LMS user_id. """
        user = self.create_user()
        user.tracking_context = self.TEST_CONTEXT
        user.save()

        initial_lms_user_id = user.lms_user_id
        self.assertIsNotNone(initial_lms_user_id)

        new_lms_user_id = 10293
        UserSocialAuth.objects.create(user=user, provider='edx-oauth2', extra_data={'user_id': new_lms_user_id})

        same_user = User.objects.get(id=user.id)
        self.assertEqual(initial_lms_user_id, same_user.lms_user_id)

        self._process_view(same_user)
        same_user = User.objects.get(id=user.id)
        self.assertEqual(initial_lms_user_id, same_user.lms_user_id)

    def test_no_lms_user_id(self):
        """ Test that middleware raises an exception for a missing LMS user_id. """
        user = self.create_user(lms_user_id=None)
        same_user = User.objects.get(id=user.id)

        with self.assertRaises(MissingLmsUserIdException):
            self._process_view(same_user)

        same_user = User.objects.get(id=user.id)
        self.assertIsNone(same_user.lms_user_id)

    @override_switch(ALLOW_MISSING_LMS_USER_ID, active=True)
    def test_no_lms_user_id_allow_missing(self):
        """ Test that middleware logs a missing LMS user_id if the switch is on. """
        user = self.create_user(lms_user_id=None)
        expected = [
            (
                self.MODEL_LOGGER_NAME,
                'INFO',
                'Could not find lms_user_id for user {}. Missing lms_user_id is allowed. Called from middleware with '
                'request path: /, referrer: None'
                .format(user.id)
            ),
        ]

        same_user = User.objects.get(id=user.id)
        with LogCapture(self.MODEL_LOGGER_NAME) as log:
            self._process_view(same_user)
            log.check_present(*expected)

        same_user = User.objects.get(id=user.id)
        self.assertIsNone(same_user.lms_user_id)

    @override_switch(ALLOW_MISSING_LMS_USER_ID, active=True)
    def test_lms_user_id_exception_allow_missing(self):
        """ Test that middleware logs an exception when looking for the LMS user_id. """
        user = self.create_user(lms_user_id=None)
        UserSocialAuth.objects.create(user=user, provider='edx-oauth2', extra_data=None)
        expected = [
            (
                self.MODEL_LOGGER_NAME,
                'WARNING',
                'Exception retrieving lms_user_id from social_auth for user {}.'.format(user.id)
            ),
        ]

        same_user = User.objects.get(id=user.id)
        with LogCapture(self.MODEL_LOGGER_NAME) as log:
            self._process_view(same_user)
            log.check_present(*expected)

        same_user = User.objects.get(id=user.id)
        self.assertIsNone(same_user.lms_user_id)
