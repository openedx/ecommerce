# -*- coding: utf-8 -*-
"""
Tests for the CacheUtilsMiddleware.
"""
from django.test import RequestFactory
from mock import MagicMock

from ecommerce.cache_utils import middleware
from ecommerce.cache_utils.utils import FORCE_CACHE_MISS_PARAM, SHOULD_FORCE_CACHE_MISS_KEY, RequestCache
from ecommerce.tests.testcases import TestCase

TEST_KEY = "clobert"
EXPECTED_VALUE = "bertclob"
TEST_NAMESPACE = "test_namespace"


class TestCacheUtilsMiddleware(TestCase):

    def setUp(self):
        super(TestCacheUtilsMiddleware, self).setUp()
        self.middleware = middleware.CacheUtilsMiddleware()
        self.request = RequestFactory().get('/')
        self.request.user = self._mock_user(is_staff=True)

        self.request_cache = RequestCache()
        self.other_request_cache = RequestCache(TEST_NAMESPACE)
        self._dirty_request_cache()

    def test_process_request(self):
        self.middleware.process_request(self.request)

        self._check_request_caches_cleared()
        self.assertFalse(self.request_cache.get_cached_response(SHOULD_FORCE_CACHE_MISS_KEY).value)

    def test_process_request_force_django_cache_miss(self):
        request = RequestFactory().get('/?{}=tRuE'.format(FORCE_CACHE_MISS_PARAM))
        request.user = self._mock_user(is_staff=True)

        self.middleware.process_request(request)

        self._check_request_caches_cleared()
        self.assertTrue(self.request_cache.get_cached_response(SHOULD_FORCE_CACHE_MISS_KEY).value)

    def test_process_request_force_django_cache_miss_non_staff(self):
        request = RequestFactory().get('/?{}=tRuE'.format(FORCE_CACHE_MISS_PARAM))
        request.user = self._mock_user(is_staff=False)

        self.middleware.process_request(request)

        self._check_request_caches_cleared()
        self.assertFalse(self.request_cache.get_cached_response(SHOULD_FORCE_CACHE_MISS_KEY).value)

    def test_process_response(self):
        response = self.middleware.process_response(self.request, EXPECTED_VALUE)

        self.assertEqual(response, EXPECTED_VALUE)
        self._check_request_caches_cleared()

    def test_process_exception(self):
        response = self.middleware.process_exception(self.request, EXPECTED_VALUE)

        self.assertEqual(response, None)
        self._check_request_caches_cleared()

    def _check_request_caches_cleared(self):
        """ Checks that all request caches were cleared. """
        self.assertTrue(self.request_cache.get_cached_response(TEST_KEY).is_miss)
        self.assertTrue(self.other_request_cache.get_cached_response(TEST_KEY).is_miss)

    def _dirty_request_cache(self):
        """ Dirties the request caches to ensure the middleware is clearing it. """
        self.request_cache.set(TEST_KEY, EXPECTED_VALUE)
        self.other_request_cache.set(TEST_KEY, EXPECTED_VALUE)

    def _mock_user(self, is_staff=True):
        mock_user = MagicMock()
        mock_user.is_active = True
        mock_user.is_staff = is_staff
        return mock_user
