# -*- coding: utf-8 -*-
"""
Tests for the request cache.
"""
import mock

from ecommerce.cache_utils.utils import CACHE_MISS, CacheMissError, RequestCache, TieredCache
from ecommerce.tests.testcases import TestCase

TEST_KEY = "clobert"
EXPECTED_VALUE = "bertclob"
DEFAULT_VALUE = "default_value"
TEST_DJANGO_TIMEOUT_CACHE = 1


class TestRequestCache(TestCase):
    def setUp(self):
        RequestCache.clear()

    def test_get_value_or_cache_miss_hit(self):
        RequestCache.set(TEST_KEY, EXPECTED_VALUE)
        cached_value = RequestCache.get_value_or_cache_miss(TEST_KEY)
        self.assertEqual(cached_value, EXPECTED_VALUE)

    def test_get_value_or_cache_miss_miss(self):
        cached_value = RequestCache.get_value_or_cache_miss(TEST_KEY)
        self.assertEqual(cached_value, CACHE_MISS)

    def test_get_value_or_default_hit(self):
        RequestCache.set(TEST_KEY, EXPECTED_VALUE)
        cached_value = RequestCache.get_value_or_default(TEST_KEY, DEFAULT_VALUE)
        self.assertEqual(cached_value, EXPECTED_VALUE)

    def test_get_value_or_default_miss(self):
        cached_value = RequestCache.get_value_or_default(TEST_KEY, DEFAULT_VALUE)
        self.assertEqual(cached_value, DEFAULT_VALUE)

    def test_set(self):
        RequestCache.set(TEST_KEY, EXPECTED_VALUE)
        self.assertEqual(RequestCache.get_value_or_cache_miss(TEST_KEY), EXPECTED_VALUE)


class TestTieredCache(TestCase):
    def setUp(self):
        RequestCache.clear()

    def test_get_value_or_cache_miss_all_tier_miss(self):
        cached_value = TieredCache.get_value_or_cache_miss(TEST_KEY)
        self.assertEqual(cached_value, CACHE_MISS)

    def test_get_value_or_cache_miss_request_cache_hit(self):
        RequestCache.set(TEST_KEY, EXPECTED_VALUE)
        cached_value = TieredCache.get_value_or_cache_miss(TEST_KEY)
        self.assertEqual(cached_value, EXPECTED_VALUE)

    @mock.patch('django.core.cache.cache.get')
    def test_get_value_or_cache_miss_django_cache_hit(self, mock_cache_get):
        mock_cache_get.return_value = EXPECTED_VALUE
        cached_value = TieredCache.get_value_or_cache_miss(TEST_KEY)
        self.assertEqual(cached_value, EXPECTED_VALUE)
        self.assertEqual(RequestCache.get_value_or_cache_miss(TEST_KEY), EXPECTED_VALUE)

    @mock.patch('django.core.cache.cache.get')
    def test_get_value_or_cache_miss_force_django_cache_miss(self, mock_cache_get):
        RequestCache.set('force_django_cache_miss', True)
        mock_cache_get.return_value = EXPECTED_VALUE
        cached_value = TieredCache.get_value_or_cache_miss(TEST_KEY)
        self.assertEqual(cached_value, CACHE_MISS)
        self.assertEqual(RequestCache.get_value_or_cache_miss(TEST_KEY), CACHE_MISS)

    def test_get_value_or_default_all_tier_miss(self):
        cached_value = TieredCache.get_value_or_default(TEST_KEY, DEFAULT_VALUE)
        self.assertEqual(cached_value, DEFAULT_VALUE)

    def test_get_value_or_default_request_cache_hit(self):
        RequestCache.set(TEST_KEY, EXPECTED_VALUE)
        cached_value = TieredCache.get_value_or_default(TEST_KEY, DEFAULT_VALUE)
        self.assertEqual(cached_value, EXPECTED_VALUE)

    @mock.patch('django.core.cache.cache.get')
    def test_get_value_or_default_django_cache_hit(self, mock_cache_get):
        mock_cache_get.return_value = EXPECTED_VALUE
        cached_value = TieredCache.get_value_or_default(TEST_KEY, DEFAULT_VALUE)
        self.assertEqual(cached_value, EXPECTED_VALUE)
        self.assertEqual(RequestCache.get_value_or_cache_miss(TEST_KEY), EXPECTED_VALUE)

    @mock.patch('django.core.cache.cache.get')
    def test_get_value_or_default_force_django_cache_miss(self, mock_cache_get):
        RequestCache.set('force_django_cache_miss', True)
        mock_cache_get.return_value = EXPECTED_VALUE
        cached_value = TieredCache.get_value_or_default(TEST_KEY, DEFAULT_VALUE)
        self.assertEqual(cached_value, DEFAULT_VALUE)
        self.assertEqual(RequestCache.get_value_or_cache_miss(TEST_KEY), CACHE_MISS)

    @mock.patch('django.core.cache.cache.set')
    def test_set_all_tiers(self, mock_cache_set):
        mock_cache_set.return_value = EXPECTED_VALUE
        TieredCache.set_all_tiers(TEST_KEY, EXPECTED_VALUE, TEST_DJANGO_TIMEOUT_CACHE)
        mock_cache_set.assert_called_with(TEST_KEY, EXPECTED_VALUE, TEST_DJANGO_TIMEOUT_CACHE)
        self.assertEqual(RequestCache.get_value_or_cache_miss(TEST_KEY), EXPECTED_VALUE)


class CacheUtilityTests(TestCase):
    def test_miss_cache_valid_use(self):
        """ Test the valid uses of CACHE_MISS. """
        self.assertTrue(CACHE_MISS is CACHE_MISS)

    def test_miss_cache_invalid_use(self):
        """ Test invalid uses of CACHE_MISS. """
        with self.assertRaises(CacheMissError):
            bool(CACHE_MISS)

        with self.assertRaises(CacheMissError):
            # For Python 3
            CACHE_MISS.__bool__()

        with self.assertRaises(CacheMissError):
            CACHE_MISS.get('x')

        with self.assertRaises(CacheMissError):
            CACHE_MISS.x = None

        with self.assertRaises(CacheMissError):
            CACHE_MISS['key']  # pylint: disable=pointless-statement

        with self.assertRaises(CacheMissError):
            CACHE_MISS['key'] = None

        with self.assertRaises(CacheMissError):
            [0, 1][CACHE_MISS]  # pylint: disable=expression-not-assigned, pointless-statement

        with self.assertRaises(CacheMissError):
            'x' in CACHE_MISS  # pylint: disable=pointless-statement

        with self.assertRaises(CacheMissError):
            for x in CACHE_MISS:  # pylint: disable=unused-variable
                pass

    def test_miss_cache_repr(self):
        """ Test the valid uses of CACHE_MISS. """
        self.assertEqual(CACHE_MISS.__repr__(), 'CACHE_MISS')
