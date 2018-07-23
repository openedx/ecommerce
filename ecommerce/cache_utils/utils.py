"""
Cache utilities.
"""
import threading

from django.core.cache import cache as django_cache
from django.core.cache.backends.base import DEFAULT_TIMEOUT

FORCE_CACHE_MISS_PARAM = 'force_cache_miss'
SHOULD_FORCE_CACHE_MISS_KEY = 'cache_utils.should_force_cache_miss'
DEFAULT_NAMESPACE = 'cache_utils.default'

_CACHE_MISS = object()


class _RequestCache(threading.local):
    """
    A thread-local for storing the per-request caches.

    The data is a dict of dicts, keyed by namespace.
    """
    _data = {}

    @classmethod
    def clear(cls):
        cls._data = {}

    @classmethod
    def get_data(cls, namespace):
        """
        Gets the thread.local data (dict) for a given namespace.

        Args:
            namespace: The namespace, or key, of the data dict.

        Returns:
            (dict)

        """
        if namespace in cls._data:
            return cls._data[namespace]
        else:
            new_data = {}
            cls._data[namespace] = new_data
            return new_data


class RequestCache(object):
    """
    A namespaced request cache for caching per-request data.
    """

    def __init__(self, namespace=None):
        """
        Creates a request cache with the provided namespace.

        Args:
            namespace (string): (optional) uses 'default' if not provided.
        """
        assert namespace != DEFAULT_NAMESPACE, 'Optional namespace can not be {}.'.format(DEFAULT_NAMESPACE)
        self.namespace = namespace or DEFAULT_NAMESPACE

    @classmethod
    def clear_all_namespaces(cls):
        """
        Clears the data for all namespaces.
        """
        _RequestCache.clear()

    def clear(self):
        """
        Clears data for the namespaced request cache.
        """
        self._get_data().clear()

    def get_cached_response(self, key):
        """
        Retrieves a CachedResponse for the provided key.

        Args:
            key (string)

        Returns:
            A CachedResponse with hit/miss status and value.

        """
        cached_value = self._get_data().get(key, _CACHE_MISS)
        is_miss = cached_value is _CACHE_MISS
        return CachedResponse(is_miss, cached_value)

    def set(self, key, value):
        """
        Caches the value for the provided key.

        Args:
            key (string)
            value (object)

        """
        self._get_data()[key] = value

    def delete(self, key):
        """
        Deletes the cached value for the provided key.

        Args:
            key (string)

        """
        if key in self._get_data():
            del self._get_data()[key]

    def _get_data(self):
        """
        Returns:
            (dict): The data for this namespaced cache.
        """
        return _RequestCache.get_data(self.namespace)


DEFAULT_REQUEST_CACHE = RequestCache()


class TieredCache(object):
    """
    A two tiered caching object with a request cache backed by a django cache.
    """

    @classmethod
    def get_cached_response(cls, key):
        """
        Retrieves a CachedResponse for the provided key.

        Args:
            key (string)

        Returns:
            A CachedResponse with hit/miss status and value.

        """
        request_cached_response = DEFAULT_REQUEST_CACHE.get_cached_response(key)
        if request_cached_response.is_miss:
            django_cached_response = cls._get_cached_response_from_django_cache(key)
            cls._set_request_cache_if_django_cache_hit(key, django_cached_response)
            return django_cached_response

        return request_cached_response

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
        DEFAULT_REQUEST_CACHE.set(key, value)
        django_cache.set(key, value, django_cache_timeout)

    @staticmethod
    def delete_all_tiers(key):
        """
        Deletes the cached value for the provided key in both the request cache and the
        django cache.

        Args:
            key (string)

        """
        DEFAULT_REQUEST_CACHE.delete(key)
        django_cache.delete(key)

    @staticmethod
    def dangerous_clear_all_tiers():
        """
        This clears both the default request cache and the entire django
        backing cache.

        Important: This should probably only be called for testing purposes.
        """
        DEFAULT_REQUEST_CACHE.clear()
        django_cache.clear()

    @staticmethod
    def _get_cached_response_from_django_cache(key):
        """
        Retrieves a CachedResponse for the given key from the django cache.

        If the request was set to force cache misses, then this will always
        return a cache miss response.

        Args:
            key (string)

        Returns:
            A CachedResponse with hit/miss status and value.

        """
        if TieredCache._should_force_django_cache_miss():
            return CACHE_MISS_RESPONSE

        cached_value = django_cache.get(key, _CACHE_MISS)
        is_miss = cached_value is _CACHE_MISS
        return CachedResponse(is_miss, cached_value)

    @staticmethod
    def _set_request_cache_if_django_cache_hit(key, django_cached_response):
        """
        Sets the value in the request cache if the django cached response was a hit.

        Args:
            key (string)
            django_cached_response (CachedResponse)

        """
        if django_cached_response.is_hit:
            DEFAULT_REQUEST_CACHE.set(key, django_cached_response.value)

    @staticmethod
    def _get_and_set_force_cache_miss(request):
        """
        Gets value for request query parameter FORCE_CACHE_MISS
        and sets it in the default request cache.

        This functionality is only available for staff.

        Example:
            http://clobert.com/api/v1/resource?force_cache_miss=true

        """
        if not (request.user and request.user.is_active and request.user.is_staff):
            force_cache_miss = False
        else:
            force_cache_miss = request.GET.get(FORCE_CACHE_MISS_PARAM, 'false').lower() == 'true'
        DEFAULT_REQUEST_CACHE.set(SHOULD_FORCE_CACHE_MISS_KEY, force_cache_miss)

    @classmethod
    def _should_force_django_cache_miss(cls):
        """
        Returns True if the tiered cache should force a cache miss for the
        django cache, and False otherwise.

        """
        cached_response = DEFAULT_REQUEST_CACHE.get_cached_response(SHOULD_FORCE_CACHE_MISS_KEY)
        return False if cached_response.is_miss else cached_response.value


class CachedResponseError(Exception):
    """
    Error used when CachedResponse is misused.
    """
    USAGE_MESSAGE = 'CachedResponse was misused. Only use the attributes is_hit (or is_miss) and value.'

    def __init__(self, message=USAGE_MESSAGE):
        super(CachedResponseError, self).__init__(message)


class CachedResponse(object):
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
        return 'CachedResponse (is_hit={})'.format(self.is_hit)

    @property
    def is_hit(self):
        return not self.is_miss

    def __nonzero__(self):
        raise CachedResponseError()

    def __bool__(self):
        raise CachedResponseError()

    def __index__(self):
        raise CachedResponseError()

    def __getattr__(self, name):
        raise CachedResponseError()

    def __setattr__(self, name, val):
        if name not in self.VALID_ATTRIBUTES:
            raise CachedResponseError()
        return super(CachedResponse, self).__setattr__(name, val)

    def __getitem__(self, key):
        raise CachedResponseError()

    def __setitem__(self, key, val):
        raise CachedResponseError()

    def __iter__(self):
        raise CachedResponseError()

    def __contains__(self, value):
        raise CachedResponseError()


CACHE_MISS_RESPONSE = CachedResponse(True, None)
