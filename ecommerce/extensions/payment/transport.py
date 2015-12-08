import io

import requests
from suds.transport import Reply
from suds.transport.http import HttpAuthenticated


class RequestsTransport(HttpAuthenticated):
    """
    HTTP transport utilizing requests library.

    This class uses requests, instead of urllib2, to make HTTP requests. This allows us to properly
    verify SSL certificates. This has been adapted from
    http://stackoverflow.com/questions/6277027/suds-over-https-with-cert.
    """
    def open(self, request):
        """ Fetch the WSDL using requests. """
        self.addcredentials(request)
        resp = requests.get(request.url, data=request.message, headers=request.headers)
        result = io.StringIO(resp.content.decode('utf-8'))
        return result

    def send(self, request):
        """ POST to the service using requests. """
        self.addcredentials(request)
        resp = requests.post(request.url, data=request.message, headers=request.headers)
        result = Reply(resp.status_code, resp.headers, resp.content)
        return result
