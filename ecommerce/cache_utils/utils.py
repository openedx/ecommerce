"""
Cache utilities.
"""
import threading

from django.core.cache import cache as django_cache
from django.core.cache.backends.base import DEFAULT_TIMEOUT

SHOULD_FORCE_CACHE_MISS_KEY = 'cache_utils.should_force_cache_miss'
FORCE_CACHE_MISS_PARAM = 'force_cache_miss'

_CACHE_MISS = object()


class RequestCache(threading.local):
    """
    A thread-local for storing the per-request cache.
    """

    _data = {}

    def __init__(self):
        super(RequestCache, self).__init__()

    @classmethod
    def clear(cls):
        cls._data = {}

    @classmethod
    def get_cache_response(cls, key):
        """
        Retrieves a CacheResponse for the provided key.

        Args:
            key (string)

        Returns:
            A CacheResponse with hit/miss status and value.

        """
        cached_value = cls._data.get(key, _CACHE_MISS)
        is_miss = cached_value is _CACHE_MISS
        return CacheResponse(is_miss, cached_value)

    @classmethod
    def set(cls, key, value):
        """
        Caches the value for the provided key.

        Args:
            key (string)
            value (object)

        """
        cls._data[key] = value

    @classmethod
    def delete(cls, key):
        """
        Deletes the cached value for the provided key.

        Args:
            key (string)

        """
        if key in cls._data:
            del cls._data[key]


class TieredCache(object):
    """
    A two tiered caching object with a request cache backed by a django cache.
    """

    @classmethod
    def get_cache_response(cls, key):
        """
        Retrieves a CacheResponse for the provided key.

        Args:
            key (string)

        Returns:
            A CacheResponse with hit/miss status and value.

        """
        request_cache_response = RequestCache.get_cache_response(key)
        if request_cache_response.is_miss:
            django_cached_response = cls._get_cache_response_from_django_cache(key)
            cls._set_request_cache_if_django_cache_hit(key, django_cached_response)
            return django_cached_response

        return request_cache_response

    @staticmethod
    def set_all_tiers(key, value, django_cache_timeout=DEFAULT_TIMEOUT):
        """
        Caches the value for the provided key in both the request cache and the
        django cache.

        Args:
            key (string)
            value (object)
            django_cache_timeout (int): (Optional) Timeout used to determine
                if and for how long to cache in the django cache. A timeout of
                0 will skip the django cache. If timeout is provided, use that
                timeout for the key; otherwise use the default cache timeout.

        """
        RequestCache.set(key, value)
        django_cache.set(key, value, django_cache_timeout)

    @staticmethod
    def delete_all_tiers(key):
        """
        Deletes the cached value for the provided key in both the request cache and the
        django cache.

        Args:
            key (string)

        """
        RequestCache.delete(key)
        django_cache.delete(key)

    @staticmethod
    def clear_all_tiers():
        """
        This clears both the test cache and the backing cache.
        Important: This will probably only be called for testing purposes.
        """
        RequestCache.clear()
        django_cache.clear()

    @classmethod
    def _get_cache_response_from_django_cache(cls, key):
        """
        Retrieves a CacheResponse for the given key from the django cache.

        If the request was set to force cache misses, then this will always
        return a cache miss response.

        Args:
            key (string)

        Returns:
            A CacheResponse with hit/miss status and value.

        """
        if cls._should_force_django_cache_miss():
            return CACHE_MISS_RESPONSE

        cached_value = django_cache.get(key, _CACHE_MISS)
        is_miss = cached_value is _CACHE_MISS
        return CacheResponse(is_miss, cached_value)

    @classmethod
    def _set_request_cache_if_django_cache_hit(cls, key, django_cache_response):
        """
        Sets the value in the request cache if the django cache response was a hit.

        Args:
            key (string)
            django_cache_response (CacheResponse)

        """
        if django_cache_response.is_hit:
            RequestCache.set(key, django_cache_response.value)

    @staticmethod
    def _get_and_set_force_cache_miss(request):
        """
        Gets value for request query parameter FORCE_CACHE_MISS
        and sets it in the request cache.

        Example:
            http://clobert.com/api/v1/resource?force_cache_miss=true

        """
        force_cache_miss = request.GET.get(FORCE_CACHE_MISS_PARAM, 'false').lower() == 'true'
        RequestCache.set(SHOULD_FORCE_CACHE_MISS_KEY, force_cache_miss)

    @classmethod
    def _should_force_django_cache_miss(cls):
        cache_response = RequestCache.get_cache_response(SHOULD_FORCE_CACHE_MISS_KEY)
        return False if cache_response.is_miss else cache_response.value


class CacheResponseError(Exception):
    """
    Error used when CacheResponse is misused.
    """
    USAGE_MESSAGE = 'CacheResponse was misused. Only use the attributes is_hit (or is_miss) and value.'

    def __init__(self, message=USAGE_MESSAGE):
        super(CacheResponseError, self).__init__(message)


class CacheResponse(object):
    """
    Represents a cache response including hit status and value.
    """
    VALID_ATTRIBUTES = ['is_miss', 'is_hit', 'value']

    def __init__(self, is_miss, value):
        self.is_miss = is_miss
        if self.is_hit:
            self.value = value

    def __repr__(self):
        # Important: Do not include the cached value to help avoid any security
        # leaks that could happen if these are logged.
        return 'CacheResponse (is_hit={})'.format(self.is_hit)

    @property
    def is_hit(self):
        return not self.is_miss

    def __nonzero__(self):
        raise CacheResponseError()

    def __bool__(self):
        raise CacheResponseError()

    def __index__(self):
        raise CacheResponseError()

    def __getattr__(self, name):
        raise CacheResponseError()

    def __setattr__(self, name, val):
        if name not in self.VALID_ATTRIBUTES:
            raise CacheResponseError()
        return super(CacheResponse, self).__setattr__(name, val)

    def __getitem__(self, key):
        raise CacheResponseError()

    def __setitem__(self, key, val):
        raise CacheResponseError()

    def __iter__(self):
        raise CacheResponseError()

    def __contains__(self, value):
        raise CacheResponseError()


CACHE_MISS_RESPONSE = CacheResponse(True, None)
