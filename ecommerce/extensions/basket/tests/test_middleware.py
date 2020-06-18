

import mock
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.test.client import RequestFactory
from oscar.core.loading import get_model
from oscar.test.factories import BasketFactory

from ecommerce.extensions.basket import middleware
from ecommerce.tests.testcases import TestCase

Basket = get_model('basket', 'Basket')


class BasketMiddlewareTests(TestCase):
    @staticmethod
    def get_response_for_test(request=None):  # pylint: disable=unused-argument
        return HttpResponse()

    def setUp(self):
        super(BasketMiddlewareTests, self).setUp()
        self.middleware = middleware.BasketMiddleware(self.get_response_for_test)
        self.request = RequestFactory().get('/')
        self.request.user = AnonymousUser()
        self.request.site = self.site
        self.middleware(self.request)

    def test_basket_is_attached_to_request(self):
        self.assertTrue(hasattr(self.request, 'basket'))

    def test_strategy_is_attached_to_basket(self):
        self.assertTrue(hasattr(self.request.basket, 'strategy'))

    def test_strategy_is_attached_to_request(self):
        self.assertTrue(hasattr(self.request, 'strategy'))

    def test_get_cookie_basket_handles_invalid_signatures(self):
        request_factory = RequestFactory()
        request_factory.cookies['oscar_open_basket'] = '1:NOTAVALIDHASH'
        request = request_factory.get('/')
        request.cookies_to_delete = []

        cookie_basket = self.middleware.get_cookie_basket("oscar_open_basket", request, None)

        self.assertEqual(None, cookie_basket)
        self.assertIn("oscar_open_basket", request.cookies_to_delete)

    @mock.patch('edx_django_utils.monitoring.set_custom_metric')
    def test_get_basket_with_single_existing_basket(self, mock_set_custom_metric):
        """ If the user already has one open basket, verify the middleware returns the basket. """
        self.request.user = self.create_user()
        basket = BasketFactory(owner=self.request.user, site=self.site)
        self.assertEqual(basket, self.middleware.get_basket(self.request))
        mock_set_custom_metric.assert_called_with('basket_id', basket.id)

    def test_get_basket_with_multiple_existing_baskets(self):
        """ If the user already has multiple open baskets, verify the middleware merges the existing
        baskets, and returns the merged basket. """
        self.request.user = self.create_user()
        basket = BasketFactory(owner=self.request.user, site=self.site)
        basket2 = BasketFactory(owner=self.request.user, site=self.site)
        self.assertEqual(basket, self.middleware.get_basket(self.request))

        # The latter baskets should always be merged into the earlier basket.
        basket2 = Basket.objects.get(id=basket2.id)
        self.assertEqual(basket2.status, Basket.MERGED)

    def test_get_basket_with_siteless_basket(self):
        """ Verify the method should ignores baskets without a site. """
        self.request.user = self.create_user()
        basket = BasketFactory(owner=self.request.user, site=self.site)
        siteless_basket = BasketFactory(owner=self.request.user, status=Basket.OPEN)
        self.assertEqual(basket, self.middleware.get_basket(self.request))

        # Verify the site-less basket is unchanged
        actual = Basket.objects.get(id=siteless_basket.id)
        self.assertEqual(siteless_basket, actual)
        self.assertEqual(siteless_basket.status, Basket.OPEN)

    @mock.patch('edx_django_utils.monitoring.set_custom_metric')
    def test_get_basket_cache(self, mock_set_custom_metric):
        """ Verify subsequent calls to the method utilize the middleware's memoization/caching. """
        # pylint: disable=protected-access
        self.request.user = self.create_user()
        basket = BasketFactory(owner=self.request.user, site=self.site)
        self.assertIsNone(self.request._basket_cache)
        self.middleware.get_basket(self.request)
        self.assertEqual(self.request._basket_cache, basket)
        self.assertEqual(self.middleware.get_basket(self.request), self.request._basket_cache)
        mock_set_custom_metric.assert_called_with('basket_id', basket.id)

    def test_get_basket_with_anonymous_user(self):
        """ Verify a new basket is created for anonymous users without cookies. """
        basket = self.middleware.get_basket(self.request)
        self.assertEqual(basket.site, self.site)
        self.assertIsNone(basket.owner)

    def test_get_cookie_key(self):
        """ Verify the method returns a site-specific key. """
        expected = '{base}_{site_id}'.format(base=settings.OSCAR_BASKET_COOKIE_OPEN, site_id=self.site.id)
        self.assertEqual(self.middleware.get_cookie_key(self.request), expected)
