from django.test.client import RequestFactory

from ecommerce.extensions.analytics import middleware
from ecommerce.tests.testcases import TestCase


class TrackingMiddlewareTests(TestCase):
    """ Test for TrackingMiddleware. """
    def setUp(self):
        super(TrackingMiddlewareTests, self).setUp()
        self.middleware = middleware.TrackingMiddleware()
        self.request_factory = RequestFactory()
        self.user = self.create_user()

    def _assert_ga_client_id(self, ga_client_id):
        self.request_factory.cookies['_ga'] = 'GA1.2.{}'.format(ga_client_id)
        request = self.request_factory.get('/')
        request.user = self.user
        self.middleware.process_request(request)
        expected_client_id = self.user.tracking_context.get('ga_client_id')
        self.assertEqual(ga_client_id, expected_client_id)

    def test_process_request(self):
        """ Test that middleware save/update GA client id in user tracking context. """
        self.assertIsNone(self.user.tracking_context)
        self._assert_ga_client_id('test-client-id')

        updated_client_id = 'updated-client-id'
        self.assertNotEqual(updated_client_id, self.user.tracking_context.get('ga_client_id'))
        self._assert_ga_client_id(updated_client_id)
