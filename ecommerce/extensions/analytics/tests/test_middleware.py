from django.test.client import RequestFactory
from social_django.models import UserSocialAuth
from testfixtures import LogCapture

from ecommerce.core.models import User
from ecommerce.extensions.analytics import middleware
from ecommerce.tests.testcases import TestCase


class TrackingMiddlewareTests(TestCase):
    """ Test for TrackingMiddleware. """
    TEST_CONTEXT = {'foo': 'bar', 'baz': None, 'lms_user_id': 12345}
    LOGGER_NAME = 'ecommerce.extensions.analytics.middleware'

    def setUp(self):
        super(TrackingMiddlewareTests, self).setUp()
        self.middleware = middleware.TrackingMiddleware()
        self.request_factory = RequestFactory()
        self.user = self.create_user()

    def _process_request(self, user):
        request = self.request_factory.get('/')
        request.user = user
        self.middleware.process_request(request)

    def _assert_ga_client_id(self, ga_client_id):
        self.request_factory.cookies['_ga'] = 'GA1.2.{}'.format(ga_client_id)
        self._process_request(self.user)
        expected_client_id = self.user.tracking_context.get('ga_client_id')
        self.assertEqual(ga_client_id, expected_client_id)

    def test_save_ga_client_id(self):
        """ Test that middleware save/update GA client id in user tracking context. """
        self.assertIsNone(self.user.tracking_context)
        self._assert_ga_client_id('test-client-id')

        updated_client_id = 'updated-client-id'
        self.assertNotEqual(updated_client_id, self.user.tracking_context.get('ga_client_id'))
        self._assert_ga_client_id(updated_client_id)

    def test_social_auth_lms_user_id_(self):
        """ Test that middleware saves the LMS user_id from the social auth. """
        user = self.create_user()
        user.tracking_context = self.TEST_CONTEXT
        user.save()

        lms_user_id = 67890
        UserSocialAuth.objects.create(user=user, extra_data={'user_id': lms_user_id})

        same_user = User.objects.get(id=user.id)
        self.assertIsNone(same_user.lms_user_id)

        self._process_request(same_user)
        same_user = User.objects.get(id=user.id)
        self.assertEqual(same_user.lms_user_id, lms_user_id)

    def test_tracking_context_lms_user_id_(self):
        """ Test that middleware saves the LMS user_id from the tracking_context. """
        user = self.create_user()
        user.tracking_context = self.TEST_CONTEXT
        user.save()

        same_user = User.objects.get(id=user.id)
        self.assertIsNone(same_user.lms_user_id)

        self._process_request(same_user)
        same_user = User.objects.get(id=user.id)
        self.assertEqual(same_user.lms_user_id, self.TEST_CONTEXT['lms_user_id'])

    def test_does_not_overwrite_lms_user_id(self):
        """ Test that middleware does not overwrite an existing LMS user_id. """
        initial_lms_user_id = 18
        user = self.create_user()
        user.tracking_context = self.TEST_CONTEXT
        user.lms_user_id = initial_lms_user_id
        user.save()

        lms_user_id = 10293
        UserSocialAuth.objects.create(user=user, extra_data={'user_id': lms_user_id})

        same_user = User.objects.get(id=user.id)
        self.assertEqual(initial_lms_user_id, same_user.lms_user_id, )

        self._process_request(same_user)
        same_user = User.objects.get(id=user.id)
        self.assertEqual(initial_lms_user_id, same_user.lms_user_id)

    def test_no_lms_user_id_(self):
        """ Test that middleware logs a missing LMS user_id. """
        user = self.create_user()
        expected = [
            (
                self.LOGGER_NAME,
                'INFO',
                'Could not find lms_user_id for user {}. Request path: /, referrer: None'.format(user.id)
            ),
        ]

        same_user = User.objects.get(id=user.id)
        with LogCapture(self.LOGGER_NAME) as log:
            self._process_request(same_user)
            log.check_present(*expected)

        same_user = User.objects.get(id=user.id)
        self.assertIsNone(same_user.lms_user_id)
