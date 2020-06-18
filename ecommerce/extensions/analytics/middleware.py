"""
Middleware for analytics app to parse the Google Analytics (GA) cookie and the LMS user_id.
"""


import logging

from django.utils.deprecation import MiddlewareMixin

from ecommerce.extensions.analytics.utils import get_google_analytics_client_id

logger = logging.getLogger(__name__)


class TrackingMiddleware(MiddlewareMixin):
    """
    Middleware that:
        1) parses the `_ga` cookie to find the GA client id and adds this to the user's tracking_context
        2) extracts the LMS user_id
        3) updates the user if necessary.

    Side effect:
        If the LMS user_id cannot be found, writes custom metrics to record this fact.

    """

    def process_view(self, request, view_func, view_args, view_kwargs):  # pylint: disable=unused-argument
        user = request.user
        if user.is_authenticated:
            tracking_context = user.tracking_context or {}

            # Check for the GA client id
            old_client_id = tracking_context.get('ga_client_id')
            ga_client_id = get_google_analytics_client_id(request)
            if ga_client_id and ga_client_id != old_client_id:
                tracking_context['ga_client_id'] = ga_client_id
                user.tracking_context = tracking_context
                user.save()

            # If the user does not already have an LMS user id, add it
            called_from = u'middleware with request path: {request}, referrer: {referrer}'.format(
                request=request.get_full_path(),
                referrer=request.META.get('HTTP_REFERER'))
            user.add_lms_user_id('ecommerce_missing_lms_user_id_middleware', called_from)
