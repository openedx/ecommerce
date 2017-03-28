import json
import logging
from functools import wraps

from threadlocals.threadlocals import get_current_request

logger = logging.getLogger(__name__)


def is_segment_configured():
    """Returns a Boolean indicating if Segment has been configured for use."""
    return bool(get_current_request().site.siteconfiguration.segment_key)


def parse_tracking_context(user):
    """Extract user ID, client ID, and IP address from a user's tracking context.

    Arguments:
        user (User): An instance of the User model.

    Returns:
        Tuple of strings: user_tracking_id, lms_client_id, lms_ip
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
    lms_ip = tracking_context.get('lms_ip')

    return user_tracking_id, lms_client_id, lms_ip


def silence_exceptions(msg):
    """Silences exceptions raised by the decorated function.

    Also logs the provided message. Used to silence exceptions raised by
    non-essential signal receivers invoked with `send()`, to prevent critical
    program flow from being interrupted.

    Arguments:
        msg (str): A message to be logged when an exception is raised.
    """
    def decorator(func):  # pylint: disable=missing-docstring
        @wraps(func)
        def wrapper(*args, **kwargs):  # pylint: disable=missing-docstring
            try:
                return func(*args, **kwargs)
            except:  # pylint: disable=bare-except
                logger.exception(msg)
        return wrapper
    return decorator


def audit_log(name, **kwargs):
    """DRY helper used to emit an INFO-level log message.

    Messages logged with this function are used to construct an audit trail. Log messages
    should be emitted immediately after the event they correspond to has occurred and, if
    applicable, after the database has been updated. These log messages use a verbose
    key-value pair syntax to make it easier to extract fields when parsing the application's
    logs.

    This function is variadic, accepting a variable number of keyword arguments.

    Arguments:
        name (str): The name of the message to log. For example, 'payment_received'.

    Keyword Arguments:
        Indefinite. Keyword arguments are strung together as comma-separated key-value
        pairs ordered alphabetically by key in the resulting log message.

    Returns:
        None
    """
    # Joins sorted keyword argument keys and values with an "=", wraps each value
    # in quotes, and separates each pair with a comma and a space.
    payload = u', '.join([u'{k}="{v}"'.format(k=k, v=v) for k, v in sorted(kwargs.items())])
    message = u'{name}: {payload}'.format(name=name, payload=payload)

    logger.info(message)


def prepare_analytics_data(user, segment_key):
    """ Helper function for preparing necessary data for analytics.

    Arguments:
        user (User): The user making the request.
        segment_key (str): Segment write/API key.

    Returns:
        str: JSON object with the data for analytics.
    """
    data = {
        'tracking': {
            'segmentApplicationId': segment_key
        }
    }

    if user.is_authenticated():
        user_tracking_id, __, __ = parse_tracking_context(user)
        user_data = {
            'user': {
                'user_tracking_id': user_tracking_id,
                'name': user.get_full_name(),
                'email': user.email
            }
        }
    else:
        user_data = {
            'user': 'AnonymousUser'
        }
    data.update(user_data)
    return json.dumps(data)
