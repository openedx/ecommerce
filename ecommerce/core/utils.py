from __future__ import unicode_literals

import hashlib
import logging

import six
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


def log_message_and_raise_validation_error(message):
    """
    Logs provided message and raises a ValidationError with the same message.

    Args:
        message (str): Message to be logged and handled by the ValidationError.

    Raises:
        ValidationError: Raise with message provided by developer.
    """
    logger.error(message)
    raise ValidationError(message)


def get_cache_key(**kwargs):
    """
    Get MD5 encoded cache key for given arguments.

    Here is the format of key before MD5 encryption.
        key1:value1__key2:value2 ...

    Example:
        >>> get_cache_key(site_domain="example.com", resource="catalogs")
        # Here is key format for above call
        # "site_domain:example.com__resource:catalogs"
        a54349175618ff1659dee0978e3149ca

    Arguments:
        **kwargs: Key word arguments that need to be present in cache key.

    Returns:
         An MD5 encoded key uniquely identified by the key word arguments.
    """
    key = '__'.join(['{}:{}'.format(item, value) for item, value in six.iteritems(kwargs)])

    return hashlib.md5(key).hexdigest()
