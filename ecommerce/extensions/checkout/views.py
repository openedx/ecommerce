""" Checkout related views. """
from __future__ import unicode_literals

from decimal import Decimal
import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.generic import RedirectView
from oscar.apps.checkout.views import *  # pylint: disable=wildcard-import, unused-wildcard-import
from oscar.core.loading import get_class, get_model

from ecommerce.core.url_utils import get_lms_url
from ecommerce.extensions.checkout.exceptions import BasketNotFreeError
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin

Applicator = get_class('offer.utils', 'Applicator')
Basket = get_model('basket', 'Basket')
logger = logging.getLogger(__name__)


class FreeCheckoutView(EdxOrderPlacementMixin, RedirectView):
    """ View to handle free checkouts.

    Retrieves the user's basket and checks to see if the basket is free in which case
    the user is redirected to the receipt page. Otherwise the user is redirected back
    to the basket summary page.
    """

    permanent = False

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(FreeCheckoutView, self).dispatch(*args, **kwargs)

    def get_redirect_url(self, *args, **kwargs):
        basket = Basket.get_basket(self.request.user, self.request.site)
        if not basket.is_empty:
            # Need to re-apply the voucher to the basket.
            Applicator().apply(basket, self.request.user, self.request)
            if basket.total_incl_tax != Decimal(0):
                raise BasketNotFreeError("Basket is not free.")

            order = self.place_free_order(basket)

            receipt_path = '{}?orderNum={}'.format(settings.RECEIPT_PAGE_PATH, order.number)
            url = get_lms_url(receipt_path)
        else:
            # If a user's basket is empty redirect the user to the basket summary
            # page which displays the appropriate message for empty baskets.
            url = reverse('basket:summary')
        return url


class CancelResponseView(RedirectView):
    """ Handles behaviour for the 'cancel' redirect. """
    permanent = False

    def get(self, request, *args, **kwargs):
        """ Retrieves the previously frozen basket from the kwargs and thaws it. """
        basket = get_object_or_404(Basket, id=kwargs['basket_id'],
                                   status=Basket.FROZEN)
        basket.thaw()
        logger.info('Payment cancelled (token %s) - basket #%s thawed',
                    request.GET.get('token', '<no token>'), basket.id)
        return super(CancelResponseView, self).get(request, *args, **kwargs)

    def get_redirect_url(self, **kwargs):
        """ Redirects back to the basket summary page. """
        return reverse('basket:summary')
