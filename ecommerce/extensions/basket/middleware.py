

import newrelic.agent
from edx_django_utils import monitoring as monitoring_utils
from oscar.apps.basket.middleware import BasketMiddleware as OscarBasketMiddleware
from oscar.core.loading import get_model

from ecommerce.extensions.basket.utils import apply_offers_on_basket

Basket = get_model('basket', 'basket')


class BasketMiddleware(OscarBasketMiddleware):
    """
    Custom Basket Middleware that overrides Oscar's Basket Middleware

    Must subclass `object` to use `super` now that `BasketMiddleware` has been
    rewritten in Django 1.11 style
    """

    def get_cookie_key(self, request):
        """
        Returns the cookie name to use for storing a cookie basket.

        Parameters:
            request (Request) -- current request being processed

        Returns:
            str - cookie name
        """
        key = super(BasketMiddleware, self).get_cookie_key(request)
        key = '{base}_{site_id}'.format(base=key, site_id=request.site.id)
        return key

    def get_basket(self, request):
        """ Return the open basket for this request """
        # pylint: disable=protected-access
        if request._basket_cache is not None:
            monitoring_utils.set_custom_metric('basket_id', request._basket_cache.id)
            return request._basket_cache

        manager = Basket.open
        cookie_key = self.get_cookie_key(request)
        cookie_basket = self.get_cookie_basket(cookie_key, request, manager)

        if hasattr(request, 'user') and request.user.is_authenticated:
            # Signed-in user: if they have a cookie basket too, it means
            # that they have just signed in and we need to merge their cookie
            # basket into their user basket, then delete the cookie.
            try:
                basket, __ = manager.get_or_create(owner=request.user, site=request.site)
            except Basket.MultipleObjectsReturned:
                # Not sure quite how we end up here with multiple baskets.
                # We merge them and create a fresh one
                old_baskets = list(manager.filter(owner=request.user, site=request.site))
                basket = old_baskets[0]
                for other_basket in old_baskets[1:]:
                    self.merge_baskets(basket, other_basket)

            # Assign user onto basket to prevent further SQL queries when
            # basket.owner is accessed.
            basket.owner = request.user

            if cookie_basket:
                self.merge_baskets(basket, cookie_basket)
                request.cookies_to_delete.append(cookie_key)

        elif cookie_basket:
            # Anonymous user with a basket tied to the cookie
            basket = cookie_basket
        else:
            # Anonymous user with no basket - instantiate a new basket instance.  No need to save yet.
            basket = Basket(site=request.site)

        # Cache basket instance for the duration of this request
        request._basket_cache = basket
        if request._basket_cache is not None:
            monitoring_utils.set_custom_metric('basket_id', request._basket_cache.id)
        else:  # pragma: no cover
            pass

        return basket

    @newrelic.agent.function_trace()
    def apply_offers_to_basket(self, request, basket):
        apply_offers_on_basket(request, basket)
