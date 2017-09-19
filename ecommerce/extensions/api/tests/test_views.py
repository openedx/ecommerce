import ddt
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase
from django.urls import reverse
from oscar.test.factories import UserFactory

from ecommerce.extensions.api.views import api_docs_permission_denied_handler


@ddt.ddt
class ApiDocsPermissionDeniedHandlerTests(TestCase):
    def setUp(self):
        super(ApiDocsPermissionDeniedHandlerTests, self).setUp()
        self.request_path = '/'
        self.request = RequestFactory().get(self.request_path)

    def test_authenticated(self):
        """ Verify the view raises `PermissionDenied` if the request is authenticated. """
        user = UserFactory()
        self.request.user = user
        self.assertRaises(PermissionDenied, api_docs_permission_denied_handler, self.request)

    @ddt.data(None, AnonymousUser())
    def test_not_authenticated(self, user):
        """ Verify the view redirects to the login page if the request is not authenticated. """
        self.request.user = user
        response = api_docs_permission_denied_handler(self.request)
        expected_url = '{path}?next={next}'.format(path=reverse('login'), next=self.request_path)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, expected_url)
