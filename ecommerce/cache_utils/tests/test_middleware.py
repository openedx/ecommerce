# -*- coding: utf-8 -*-
"""
Tests for the CacheUtilsMiddleware.
"""
from django.test import RequestFactory

from ecommerce.cache_utils import middleware
from ecommerce.cache_utils.utils import CACHE_MISS, RequestCache
from ecommerce.tests.testcases import TestCase

TEST_KEY = "clobert"
EXPECTED_VALUE = "bertclob"


class TestCacheUtilsMiddleware(TestCase):

    def setUp(self):
        super(TestCacheUtilsMiddleware, self).setUp()
        self.middleware = middleware.CacheUtilsMiddleware()
        self.request = RequestFactory().get('/')
        self._dirty_request_cache()

    def test_process_request(self):
        self.middleware.process_request(self.request)

        self.assertEqual(RequestCache.get_value_or_cache_miss(TEST_KEY), CACHE_MISS)
        self.assertFalse(RequestCache.get_value_or_cache_miss('force_django_cache_miss'))

    def test_process_request_force_django_cache_miss(self):
        request = RequestFactory().get('/?force_django_cache_miss=tRuE')

        self.middleware.process_request(request)

        self.assertEqual(RequestCache.get_value_or_cache_miss(TEST_KEY), CACHE_MISS)
        self.assertTrue(RequestCache.get_value_or_cache_miss('force_django_cache_miss'))

    def test_process_response(self):
        response = self.middleware.process_response(self.request, EXPECTED_VALUE)

        self.assertEqual(response, EXPECTED_VALUE)
        self.assertEqual(RequestCache.get_value_or_cache_miss(TEST_KEY), CACHE_MISS)

    def test_process_exception(self):
        response = self.middleware.process_exception(self.request, EXPECTED_VALUE)

        self.assertEqual(response, None)
        self.assertEqual(RequestCache.get_value_or_cache_miss(TEST_KEY), CACHE_MISS)

    @staticmethod
    def _dirty_request_cache():
        """ Dirties the request cache to ensure it is cleared later. """
        RequestCache.set(TEST_KEY, EXPECTED_VALUE)
