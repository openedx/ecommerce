from __future__ import unicode_literals

import hashlib
import logging
from urlparse import parse_qs, urlparse

import six
import waffle
from django.conf import settings
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


def deprecated_traverse_pagination(response, endpoint):
    """
    Traverse a paginated API response.

    Note: This method should be deprecated since it defeats the purpose
    of pagination.

    Extracts and concatenates "results" (list of dict) returned by DRF-powered
    APIs.

    Arguments:
        response (Dict): Current response dict from service API
        endpoint (slumber Resource object): slumber Resource object from edx-rest-api-client

    Returns:
        list of dict.

    """
    results = response.get('results', [])

    next_page = response.get('next')
    while next_page:
        if waffle.switch_is_active("debug_logging_for_deprecated_traverse_pagination"):  # pragma: no cover
            base_url = ""
            try:
                base_url = endpoint._store['base_url']  # pylint: disable=protected-access
            except:  # pylint: disable=bare-except
                pass
            logger.info("deprecated_traverse_pagination method is called for endpoint %s", base_url)
        querystring = parse_qs(urlparse(next_page).query, keep_blank_values=True)
        response = endpoint.get(**querystring)
        results += response.get('results', [])
        next_page = response.get('next')

    return results


def use_read_replica_if_available(queryset):
    """
    If there is a database called 'read_replica', use that database for the queryset.
    """
    return queryset.using("read_replica") if "read_replica" in settings.DATABASES else queryset
