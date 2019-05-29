"""
Middleware for analytics app to parse Google Analytics (GA) cookie and the lms_user_id.
"""
import logging
from ecommerce.extensions.analytics.utils import get_google_analytics_client_id

logger = logging.getLogger(__name__)


class TrackingMiddleware(object):
    """
    Middleware that parse `_ga` cookie for the user tracking context to obtain the GA client id, extracts the
    lms_user_id, and updates the user if necessary.
    """

    def process_request(self, request):
        user = request.user
        if user.is_authenticated():
            save_user = False
            tracking_context = user.tracking_context or {}

            # Check for the GA client id
            old_client_id = tracking_context.get('ga_client_id')
            ga_client_id = get_google_analytics_client_id(request)
            if ga_client_id and ga_client_id != old_client_id:
                tracking_context['ga_client_id'] = ga_client_id
                user.tracking_context = tracking_context
                save_user = True

            if not user.lms_user_id:
                # Check for the lms_user_id in social auth
                lms_user_id_social_auth = self._get_lms_user_id_from_social_auth(user)
                if lms_user_id_social_auth:
                    user.lms_user_id = lms_user_id_social_auth
                    save_user = True
                    logger.info(u'Saving lms_user_id from social auth for user %s', user.id)
                else:
                    # Check for the lms_user_id in the tracking context
                    lms_user_id_tracking_context = tracking_context.get('lms_user_id')
                    if lms_user_id_tracking_context:
                        user.lms_user_id = lms_user_id_tracking_context
                        save_user = True
                        logger.info(u'Saving lms_user_id from tracking context for user %s', user.id)

            if save_user:
                user.save()

    def _get_lms_user_id_from_social_auth(self, user):
        """
        Return LMS user_id passed through social auth, if found.
        Returns None if not found.
        """
        lms_user_id_social_auth = None
        try:
            lms_user_id_social_auth = user.social_auth.first().extra_data[u'user_id']  # pylint: disable=no-member
        except Exception:  # pylint: disable=broad-except
            pass
        return lms_user_id_social_auth
