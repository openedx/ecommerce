from threading import current_thread

_requests = {}

def get_current_request():
    return _requests.get(current_thread(), None)

def set_current_request(request=None):
    _requests[current_thread()] = request

class GlobalRequestMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        set_current_request(request)
        return self.get_response(request)
