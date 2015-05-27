from functools import wraps
import logging

from django.conf import settings


logger = logging.getLogger(__name__)


def is_segment_configured():
    """Returns a Boolean indicating if Segment has been configured for use."""
    return bool(settings.SEGMENT_KEY)


def parse_tracking_context(user):
    """Extract user and client IDs from a user's tracking context.

    Arguments:
        user (User): An instance of the User model.

    Returns:
        Tuple of strings, user_tracking_id and lms_client_id
    """
    tracking_context = user.tracking_context or {}

    user_tracking_id = tracking_context.get('lms_user_id')
    if user_tracking_id is None:
        # Even if we cannot extract a good platform user ID from the context, we can still track the
        # event with an arbitrary local user ID. However, we need to disambiguate the ID we choose
        # since there's no guarantee it won't collide with a platform user ID that may be tracked
        # at some point.
        user_tracking_id = 'ecommerce-{}'.format(user.id)

    lms_client_id = tracking_context.get('lms_client_id')

    return user_tracking_id, lms_client_id


def log_exceptions(msg):
    """Log exceptions (avoiding clutter/indentation).

    Exceptions are still raised. This module assumes that signal receivers are
    being invoked with `send_robust`, or that callers will otherwise mute
    exceptions as needed.
    """
    def decorator(func):  # pylint: disable=missing-docstring
        @wraps(func)
        def wrapper(*args, **kwargs):  # pylint: disable=missing-docstring
            try:
                return func(*args, **kwargs)
            except:  # pylint: disable=bare-except
                logger.exception(msg)
                raise
        return wrapper
    return decorator
