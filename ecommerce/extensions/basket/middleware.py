from django.contrib.sites.shortcuts import get_current_site
from oscar.apps.basket.middleware import BasketMiddleware
from oscar.core.loading import get_model

Basket = get_model('basket', 'basket')


class PartnerBasketMiddleware(BasketMiddleware):
    """In Basket model partner is added as foreign key field which is not null.
    Default middleware method get_basket() was raising exception partner id cannot
    be null. To fix this issue created new middleware and override the method.
    """

    def get_basket(self, request):
        """
        Return the open basket for this request
        """
        # The multi-tenant implementation has one site per partner

        site = get_current_site(request)
        partner = site.siteconfiguration.partner

        if request._basket_cache is not None:  # pylint: disable=protected-access
            return request._basket_cache  # pylint: disable=protected-access

        manager = Basket.open
        cookie_key = self.get_cookie_key(request)
        cookie_basket = self.get_cookie_basket(cookie_key, request, manager)

        if hasattr(request, 'user') and request.user.is_authenticated():
            # Signed-in user: if they have a cookie basket too, it means
            # that they have just signed in and we need to merge their cookie
            # basket into their user basket, then delete the cookie.
            try:
                basket, __ = manager.get_or_create(owner=request.user, partner=partner)
            except Basket.MultipleObjectsReturned:
                # Not sure quite how we end up here with multiple baskets.
                # We merge them and create a fresh one
                old_baskets = list(manager.filter(owner=request.user, partner=partner))
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
            # Anonymous user with no basket - instantiate a new basket
            # instance.  No need to save yet.
            # we need to.
            basket = Basket()

        # Cache basket instance for the during of this request
        request._basket_cache = basket  # pylint: disable=protected-access

        return basket
