

from django.conf import settings
from django.test import LiveServerTestCase as DjangoLiveServerTestCase
from django.test import TestCase as DjangoTestCase
from django.test import TransactionTestCase as DjangoTransactionTestCase
from edx_django_utils.cache import TieredCache
from oscar.test.factories import CategoryFactory

from ecommerce.tests.mixins import SiteMixin, TestServerUrlMixin, TestWaffleFlagMixin, UserMixin

# When all unit tests are run, the catalog category table will sometimes be empty. However, if only a single test
# is run, Category will have been populated by migrations (in particular, see
# ecommerce/extensions/catalogue/migrations/0002_auto_20150223_1052.py). This can lead to conflicting paths if a test
# creates more than one ProductFactory, since the CategoryFactory will attempt to reuse the path 0001.
CategoryFactory.reset_sequence(1000)


class TieredCacheMixin:
    # TODO: Once the CacheIsolationMixin and CacheIsolationTestCase from edx-platform,
    # are moved to edx-django-utils, this can be replaced.

    def setUp(self):
        TieredCache.dangerous_clear_all_tiers()
        super(TieredCacheMixin, self).setUp()

    def tearDown(self):
        TieredCache.dangerous_clear_all_tiers()
        super(TieredCacheMixin, self).tearDown()


class ViewTestMixin(TieredCacheMixin):
    path = None

    def setUp(self):
        super(ViewTestMixin, self).setUp()
        user = self.create_user(is_staff=True)
        self.client.login(username=user.username, password=self.password)

    def assert_get_response_status(self, status_code):
        """ Asserts the HTTP status of a GET responses matches the expected status. """
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, status_code)
        return response

    def test_login_required(self):
        """ Users are required to login before accessing the view. """
        self.client.logout()
        response = self.assert_get_response_status(302)
        self.assertIn(settings.LOGIN_URL, response.url)

    def test_staff_only(self):
        """ The view should only be accessible to staff. """
        self.client.logout()

        user = self.create_user(is_staff=False)
        self.client.login(username=user.username, password=self.password)
        self.assert_get_response_status(404)

        user.is_staff = True
        user.save()
        self.assert_get_response_status(200)


class TestCase(TestServerUrlMixin, UserMixin, SiteMixin, TieredCacheMixin, DjangoTestCase, TestWaffleFlagMixin):
    """
    Base test case for ecommerce tests.

    This class guarantees that tests have a Site and Partner available.
    """


class LiveServerTestCase(TestServerUrlMixin, UserMixin, SiteMixin, TieredCacheMixin, DjangoLiveServerTestCase):
    """
    Base test case for ecommerce tests.

    This class guarantees that tests have a Site and Partner available.
    """


class TransactionTestCase(TestServerUrlMixin, UserMixin, SiteMixin, TieredCacheMixin, DjangoTransactionTestCase):
    """
    Base test case for ecommerce tests.

    This class guarantees that tests have a Site and Partner available.
    """
