"""
Caching Utilities

The following caching utilities help make it simpler to properly handle caching.

Safe Cache Misses:

    An object to be used to represent a CACHE_MISS.  It should only be
    used as follows:

        value = safe_cache_get(key)
        if value is CACHE_MISS:
            value = None  # or any appropriate default
            ...

    The purpose of this code is to ensure that None is not used as the cache miss
    in places where None was also meant to sometimes be a cache hit.

"""
from django.core.cache import cache


class CacheMissError(Exception):
    """
    An error used when the CACHE_MISS object is misused in any context other
    than checking if it is the CACHE_MISS object.
    """
    USAGE_MESSAGE = 'Proper Usage: "if value is CACHE_MISS: value = DEFAULT; ...".'

    def __init__(self, message=USAGE_MESSAGE):
        super(CacheMissError, self).__init__(message)


class _CacheMiss(object):
    """
    Private class representing cache misses.  This is not meant to be used
    outside of the singleton declaration of CACHE_MISS.

    Meant to be a noisy object if used for any other purpose other than:
        if value is CACHE_MISS:
    """
    def __repr__(self):
        return 'CACHE_MISS'

    def __nonzero__(self):
        raise CacheMissError()

    def __bool__(self):
        raise CacheMissError()

    def __index__(self):
        raise CacheMissError()

    def __getattr__(self, name):
        raise CacheMissError()

    def __setattr__(self, name, val):
        raise CacheMissError()

    def __getitem__(self, key):
        raise CacheMissError()

    def __setitem__(self, key, val):
        raise CacheMissError()

    def __iter__(self):
        raise CacheMissError()

    def __contains__(self, value):
        raise CacheMissError()


# Singleton CacheMiss to be used everywhere.
CACHE_MISS = _CacheMiss()


def safe_cache_get(key):
    """
    Safely retrieves a cached value or returns the CACHE_MISS object.

    The CACHE_MISS object helps avoid the problem where a cache miss is
    represented by None, but some intended cache hits were also None, and
    instead get treated as a cache miss by mistake.

    Usage:
        value = safe_cache_get(key)
        if value is CACHE_MISS:
            value = None  # or any appropriate default
            ...

    Args:
        key (string): The key for which to retrieve a value from the cache.

    Returns: The value associated with key, or the CACHE_MISS object.

    """
    return cache.get(key, CACHE_MISS)
