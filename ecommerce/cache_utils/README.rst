Cache Utils
===========

RequestCache
------------

A thread-local for storing request scoped cache values.

An optional namespace can be used with the RequestCache, or you can use
the `DEFAULT_REQUEST_CACHE`.


TieredCache
-----------

The first tier is the default request cache that is tied to the life of a
given request. The second tier is the Django cache -- e.g. the "default"
entry in settings.CACHES, typically backed by memcached.

Some baseline rules:

1. Treat it as a global namespace, like any other cache. The per-request
   local cache is only going to live for the lifetime of one request, but
   the backing cache is going to be something like Memcached, where key
   collision is possible.

2. Timeouts are ignored for the purposes of the in-memory request cache,
   but do apply to the Django cache. One consequence of this is that
   sending an explicit timeout of 0 in `set_all_tiers` will cause that
   item to only be cached across the duration of the request and will not
   cause a write to the remote cache.

Sample Usage using is_hit::

    x_cached_response = TieredCache.get_cached_response(key)
    if x_cached_response.is_hit:
        return x_cached_response.value
     # calculate x, set in cache, and return value.

Sample Usage using is_miss::

    x_cached_response = TieredCache.get_cached_response(key)
    if x_cached_response.is_miss:
        # calculate x, set in cache, and return value.
    return x_cached_response.value


You must include 'ecommerce.cache_utils.middleware.CacheUtilsMiddleware'
for the TieredCache to work properly.

Force Django Cache Miss
^^^^^^^^^^^^^^^^^^^^^^^

To force recompute a value stored in the django cache, add the query
parameter 'force_django_cache_miss'. This will force a CACHE_MISS.

This requires staff permissions.

Example::

    http://clobert.com/api/v1/resource?force_django_cache_miss=true


CachedResponse
--------------

A CachedResponse includes the cache miss/hit status and value stored in the
cache.

The purpose of the CachedResponse is to avoid a common bug with the default
Django cache interface where a cache hit that is Falsey (e.g. None) is
misinterpreted as a cache miss.

An example of the Bug::

    cache_value = cache.get(key)
    if cache_value:
        # calculated value is None, set None in cache, and return value.
        # BUG: None will be treated as a cache miss every time.
    return  cache_value
