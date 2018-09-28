import json
import logging
from functools import wraps

from ecommerce.courses.utils import mode_for_product

logger = logging.getLogger(__name__)

ECOM_TRACKING_ID_FMT = 'ecommerce-{}'


def parse_tracking_context(user):
    """Extract user ID, client ID, and IP address from a user's tracking context.

    Arguments:
        user (User): An instance of the User model.

    Returns:
        Tuple of strings: user_tracking_id, ga_client_id, lms_ip
    """
    tracking_context = user.tracking_context or {}

    user_tracking_id = tracking_context.get('lms_user_id')
    if user_tracking_id is None:
        # Even if we cannot extract a good platform user ID from the context, we can still track the
        # event with an arbitrary local user ID. However, we need to disambiguate the ID we choose
        # since there's no guarantee it won't collide with a platform user ID that may be tracked
        # at some point.
        user_tracking_id = ECOM_TRACKING_ID_FMT.format(user.id)

    lms_ip = tracking_context.get('lms_ip')
    ga_client_id = tracking_context.get('ga_client_id')

    return user_tracking_id, ga_client_id, lms_ip


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


def track_segment_event(site, user, event, properties):
    """ Fire a tracking event via Segment.

    Args:
        site (Site): Site whose Segment client should be used.
        user (User): User to which the event should be associated.
        event (str): Event name.
        properties (dict): Event properties.

    Returns:
        (success, msg): Tuple indicating the success of enqueuing the event on the message queue.
            This can be safely ignored unless needed for debugging purposes.
    """
    if not user:
        return False, 'Event is not fired for anonymous user.'

    site_configuration = site.siteconfiguration
    if not site_configuration.segment_key:
        msg = 'Event [{event}] was NOT fired because no Segment key is set for site configuration [{site_id}]'
        msg = msg.format(event=event, site_id=site_configuration.pk)
        logger.debug(msg)
        return False, msg

    user_tracking_id, ga_client_id, lms_ip = parse_tracking_context(user)
    context = {
        'ip': lms_ip,
        'Google Analytics': {
            'clientId': ga_client_id
        }
    }
    return site.siteconfiguration.segment_client.track(user_tracking_id, event, properties, context=context)


def translate_basket_line_for_segment(line):
    """ Translates a BasketLine to Segment's expected format for cart events.

    Args:
        line (BasketLine)

    Returns:
        dict
    """
    course = line.product.course
    return {
        # For backwards-compatibility with older events the `sku` field is (ab)used to
        # store the product's `certificate_type`, while the `id` field holds the product's
        # SKU. Marketing is aware that this approach will not scale once we start selling
        # products other than courses, and will need to change in the future.
        'product_id': line.stockrecord.partner_sku,
        'sku': mode_for_product(line.product),
        'name': course.id if course else line.product.title,
        'price': str(line.line_price_excl_tax),
        'quantity': line.quantity,
        'category': line.product.get_product_class().name,
    }


def get_google_analytics_client_id(request):
    """Get google analytics client ID from request cookies."""
    if not request:
        return None

    # Google Analytics uses the clientId to keep track of unique visitors. A GA cookie looks like
    # this: _ga=GA1.2.1033501218.1368477899 and the clientId is this part: 1033501218.1368477899
    google_analytics_cookie = request.COOKIES.get('_ga')
    if google_analytics_cookie:
        return '.'.join(google_analytics_cookie.split('.')[2:])

    return None
