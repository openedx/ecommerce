from django.core.cache import cache
from django.test import LiveServerTestCase as DjangoLiveServerTestCase
from django.test import TestCase as DjangoTestCase
from django.test import TransactionTestCase as DjangoTransactionTestCase

from ecommerce.core.tests import toggle_switch
from ecommerce.tests.mixins import SiteMixin, TestServerUrlMixin, UserMixin


class CacheMixin(object):
    def setUp(self):
        cache.clear()
        super(CacheMixin, self).setUp()

    def tearDown(self):
        cache.clear()
        super(CacheMixin, self).tearDown()


class TestCase(TestServerUrlMixin, UserMixin, SiteMixin, CacheMixin, DjangoTestCase):
    """
    Base test case for ecommerce tests.

    This class guarantees that tests have a Site and Partner available.
    """
    # TODO: This is a temporary setUp which should be removed together with the switch and COURSE_CATALOG_API_URL
    # once the site-specific URL feature gets approved. This work is part of LEARNER-1135.
    def setUp(self):
        super(TestCase, self).setUp()
        toggle_switch('use_multi_tenant_discovery_api_urls', True)


class LiveServerTestCase(TestServerUrlMixin, UserMixin, SiteMixin, CacheMixin, DjangoLiveServerTestCase):
    """
    Base test case for ecommerce tests.

    This class guarantees that tests have a Site and Partner available.
    """
    pass


class TransactionTestCase(TestServerUrlMixin, UserMixin, SiteMixin, CacheMixin, DjangoTransactionTestCase):
    """
    Base test case for ecommerce tests.

    This class guarantees that tests have a Site and Partner available.
    """
    pass
