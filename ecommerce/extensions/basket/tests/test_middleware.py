from django.contrib.auth.models import AnonymousUser
from django.contrib.sites.shortcuts import get_current_site
from django.test import TestCase
from django.test.client import RequestFactory
from mock import patch
from oscar.core.loading import get_model
from oscar.test import factories

from ecommerce.extensions.basket.middleware import PartnerBasketMiddleware
from ecommerce.extensions.test.factories import BasketFactory


Basket = get_model('basket', 'basket')


class TestBasketMiddleware(TestCase):

    def setUp(self):
        self.middleware = PartnerBasketMiddleware()
        self.request = RequestFactory().get('/')
        self.request.user = AnonymousUser()
        self.middleware.process_request(self.request)

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
        self.assertIn('oscar_open_basket', request.cookies_to_delete)

    def test_get_basket_with_anonymous_user(self):
        basket = self.middleware.get_basket(self.request)
        self.assertIsNone(basket.partner)

    def test_get_basket_with_authenticated_user(self):
        self.request.user = factories.UserFactory()
        basket = self.middleware.get_basket(self.request)
        self.assertIsNotNone(basket.partner)

    def test_get_cookie_basket_with_ananoymous_user(self):
        basket = BasketFactory()
        with patch('ecommerce.extensions.basket.middleware.PartnerBasketMiddleware.get_cookie_basket') as mocked:
            mocked.return_value = basket
            self.middleware.get_basket(self.request)
            self.assertTrue(hasattr(self.request, 'basket'))

    def test_check_multiple_basket_exception(self):
        """Purpose of this test is mainly test coverage."""
        self.request.user = factories.UserFactory()
        site = get_current_site(self.request)
        partner = site.siteconfiguration.partner

        # Adding multiple baskets to check code for exception.
        BasketFactory(owner=self.request.user, partner=partner)
        BasketFactory(owner=self.request.user, partner=partner)

        with patch.object(Basket.open, 'get_or_create') as mock_method:
            mock_method.side_effect = Basket.MultipleObjectsReturned
            self.middleware.get_basket(self.request)
            self.assertTrue(hasattr(self.request, 'basket'))

    def test_get_cookie_basket_with_verified_user(self):
        self.request.user = factories.UserFactory()
        site = get_current_site(self.request)
        partner = site.siteconfiguration.partner
        # Adding multiple baskets to check code for exception .
        basket = BasketFactory(owner=self.request.user, partner=partner)
        with patch('ecommerce.extensions.basket.middleware.PartnerBasketMiddleware.get_cookie_basket') as mocked:
            mocked.return_value = basket
            self.middleware.get_basket(self.request)
            self.assertTrue(hasattr(self.request, 'basket'))

    def test_basket_cache(self):
        """Verify if request has cache basket instance than return it."""
        self.request._basket_cache = True  # pylint: disable=protected-access
        self.assertTrue(self.middleware.get_basket(self.request))  # pylint: disable=protected-access
