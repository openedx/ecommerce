import uuid

from suds.transport import Request

from ecommerce.core.tests.patched_httpretty import httpretty
from ecommerce.extensions.payment.transport import RequestsTransport
from ecommerce.tests.testcases import TestCase

API_URL = 'https://example.com/api.wsdl'
CONTENT_TYPE = 'text/plain'


class RequestsTransportTests(TestCase):
    @httpretty.activate
    def test_open(self):
        """ Verify the open method calls the API and returns the response content. """
        request = Request(API_URL)
        body = str(uuid.uuid4())
        httpretty.register_uri(httpretty.GET, API_URL, body=body, content_type=CONTENT_TYPE)

        transport = RequestsTransport()
        response = transport.open(request).getvalue()
        self.assertEqual(response, body)

    @httpretty.activate
    def test_send(self):
        """ Verify the send method POSTs data to the API and returns a Reply object. """
        request = Request(API_URL)
        body = str(uuid.uuid4())
        httpretty.register_uri(httpretty.POST,
                               API_URL,
                               body=body,
                               content_type=CONTENT_TYPE,
                               forcing_headers={'date': 'never'})

        transport = RequestsTransport()
        response = transport.send(request)

        self.assertEqual(response.code, 200)
        self.assertEqual(response.headers, {
            'date': 'never',
            'content-type': CONTENT_TYPE
        })
        self.assertEqual(response.message, body)
