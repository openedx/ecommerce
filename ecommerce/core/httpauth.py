import base64

from django.http import HttpResponse
from django.contrib.auth import authenticate


def basic_http_auth(f):
    def wrap(self, request, *args, **kwargs):
        if request.user.is_authenticated():
            return f(self, request, *args, **kwargs)
        elif 'HTTP_AUTHORIZATION' in request.META:
            auth = request.META['HTTP_AUTHORIZATION'].split()
            if len(auth) == 2:
                if auth[0].lower() == "basic":
                    username, password = base64.b64decode(auth[1]).split(':', 1)
                    user = authenticate(username=username, password=password)
                    if user is not None:
                        request.user = user
                        return f(self, request, *args, **kwargs)

        # otherwise ask for authentification
        response = HttpResponse("")
        response.status_code = 401
        response['WWW-Authenticate'] = 'Basic realm="restricted area"'
        return response

    return wrap
