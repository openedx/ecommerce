from django.test import TestCase as DjangoTestCase, LiveServerTestCase as DjangoLiveServerTestCase

from ecommerce.tests.mixins import SiteMixin, UserMixin, TestServerUrlMixin


class TestCase(TestServerUrlMixin, UserMixin, SiteMixin, DjangoTestCase):
    """
    Base test case for ecommerce tests.

    This class guarantees that tests have a Site and Partner available.
    """
    pass


class LiveServerTestCase(TestServerUrlMixin, UserMixin, SiteMixin, DjangoLiveServerTestCase):
    """
    Base test case for ecommerce tests.

    This class guarantees that tests have a Site and Partner available.
    """
    pass
