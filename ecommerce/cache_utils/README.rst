Cache Utils
===========

TieredCache
-----------

The first tier is a request cache that is tied to the life of a
given request. The second tier is the Django cache -- e.g. the
"default" entry in settings.CACHES, typically backed by memcached.

Some baseline rules:

1. Treat it as a global namespace, like any other cache. The per-request
   local cache is only going to live for the lifetime of one request, but
   the backing cache is going to be something like Memcached, where key
   collision is possible.

2. Timeouts are ignored for the purposes of the in-memory request cache,
   but do apply to the Django cache. One consequence of this is that
   sending an explicit timeout of 0 in `set` or `add` will cause that
   item to only be cached across the duration of the request and will not
   cause a write to the remote cache.

Usage::

    from ecommerce.cache_utils.utils import CACHE_MISS, TieredCache

    TieredCache.get_value_or_cache_miss(key)
    if value is CACHE_MISS:
        value = None  # or any appropriate default
        ...

        TieredCache.set_all_tiers(key, value, django_cache_timeout)

Force CACHE_MISS
^^^^^^^^^^^^^^^^

To force recompute a value stored in the django cache, add the query
parameter 'force_django_cache_miss'. This will force a CACHE_MISS.

Example::

    http://clobert.com/api/v1/resource?force_django_cache_miss=true

CACHE_MISS
----------

An object to be used to represent a CACHE_MISS.  See TieredCache.

The CACHE_MISS object avoids the problem where a cache hit that
is Falsey is misinterpreted as a cache miss.
