"""
Helper functions for working with Course Discovery Service.
"""
import hashlib
import logging

from django.conf import settings
from django.core.cache import cache

from ecommerce.services.utils import traverse_pagination


logger = logging.getLogger(__name__)


def get_course_catalogs(site, resource_id=None):
    """
    Get details related to course catalogs.

    Arguments:
        site (Site): Site object containing Site Configuration data
        resource_id (int or str): Identifies a specific resource to be retrieved

    Returns:
        dict: Course catalogs received from Course Catalog API

    """
    resource = 'catalogs'
    base_cache_key = 'catalog.api.data'

    cache_key = '{}.{}'.format(base_cache_key, resource_id) if resource_id else base_cache_key
    cache_key = hashlib.md5(cache_key).hexdigest()
    cached = cache.get(cache_key)
    if cached:
        return cached

    api = site.siteconfiguration.course_catalog_api_client
    try:
        endpoint = getattr(api, resource)
        response = endpoint(resource_id).get()

        if resource_id:
            results = response
        else:
            results = traverse_pagination(response, endpoint)
    except:  # pylint: disable=bare-except
        logger.exception('Failed to retrieve data from the Course Discovery API.')
        return []

    cache.set(cache_key, results, settings.CATALOG_API_CACHE_TIMEOUT)
    return results
