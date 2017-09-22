from django.conf import settings
from rest_framework.throttling import UserRateThrottle


class ServiceUserThrottle(UserRateThrottle):
    """A throttle allowing the service user to override rate limiting"""

    def allow_request(self, request, view):
        """Returns True if the request is coming from the service user, and
        defaults to UserRateThrottle's configured setting otherwise.
        """
        if request.user.username == settings.ECOMMERCE_SERVICE_WORKER_USERNAME:
            return True
        return super(ServiceUserThrottle, self).allow_request(request, view)
