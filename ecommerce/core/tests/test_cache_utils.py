from ecommerce.core.cache_utils import CACHE_MISS, CacheMissError
from ecommerce.tests.testcases import TestCase


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
