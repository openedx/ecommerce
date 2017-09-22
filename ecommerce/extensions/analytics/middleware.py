"""
Middleware for analytics app to parse GA cookie.
"""

from ecommerce.extensions.analytics.utils import get_google_analytics_client_id


class TrackingMiddleware(object):
    """
    Middleware that parse `_ga` cookie and save/update in user tracking context.
    """

    def process_request(self, request):
        user = request.user
        if user.is_authenticated():
            tracking_context = user.tracking_context or {}
            old_client_id = tracking_context.get('ga_client_id')
            ga_client_id = get_google_analytics_client_id(request)

            if ga_client_id and ga_client_id != old_client_id:
                tracking_context['ga_client_id'] = ga_client_id
                user.tracking_context = tracking_context
                user.save()
