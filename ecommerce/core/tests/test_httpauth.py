import base64
import ddt

from django.http import HttpResponse
from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser

from ecommerce.core.httpauth import basic_http_auth
from ecommerce.tests.testcases import TestCase


@basic_http_auth
def get(*args, **kwargs):  # pylint: disable=unused-argument
    response = HttpResponse("")
    response.status_code = 200
    return response


@ddt.ddt
class HttpBasicAuthTests(TestCase):
    def setUp(self):
        super(HttpBasicAuthTests, self).setUp()
        self.user = self.create_user()

    def _create_request(self, user=None, meta=None):
        request = RequestFactory()
        request.user = user if user is not None else self.user
        request.META = meta if meta is not None else {}
        return request

    def _create_basic_auth_header(self):
        basic_header = 'Basic ' + base64.b64encode('{user}:{password}'.format(
            user=self.user.username,
            password=self.password
        ))
        headers = {
            'HTTP_AUTHORIZATION': basic_header
        }

        return headers

    def test_basic_auth_for_session_user(self):
        request = self._create_request()
        response = get(self, request)

        self.assertEqual(response.status_code, 200)

    def test_basic_auth_for_anonymous_user_no_auth(self):
        request = self._create_request(
            user=AnonymousUser()
        )
        response = get(self, request)

        self.assertEqual(response.status_code, 401)

    @ddt.data(
        'basic too many strings',
        'doesnt start with basic',
        'basic ' + base64.b64encode('badusername:andpassword'),
    )
    def test_basic_auth_for_anonymous_user_bad_auth(self, header):
        request = self._create_request(
            user=AnonymousUser(),
            meta={'HTTP_AUTHORIZATION': header}
        )
        response = get(self, request)

        self.assertEqual(response.status_code, 401)

    def test_basic_auth_for_anonymous_user_with_auth(self):
        request = self._create_request(
            user=AnonymousUser(),
            meta=self._create_basic_auth_header()
        )
        response = get(self, request)

        self.assertEqual(response.status_code, 200)
