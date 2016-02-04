from __future__ import unicode_literals

from django.http import HttpResponseRedirect, HttpResponseBadRequest, HttpResponseServerError
from oscar.apps.basket.views import *  # pylint: disable=wildcard-import, unused-wildcard-import

from ecommerce.extensions.partner.shortcuts import get_partner_for_site

Basket = get_model('basket', 'Basket')
Selector = get_class('partner.strategy', 'Selector')
StockRecord = get_model('partner', 'StockRecord')


class BasketSingleItemView(View):
    def _prepare_basket(self, site, user, product):  # pylint: disable=unused-argument
        """
        Prepare the basket, and add the product.

        Existing baskets are merged and flushed. The specified product will be added to the remaining open basket,
        and the basket will be frozen.

        Arguments
            product(Product) -- Product to be added to the basket.
        """
        basket = Basket.get_basket(user, site)
        basket.thaw()
        basket.flush()
        basket.reset_offer_applications()
        basket.add_product(product, 1)

    def get(self, request):
        partner = get_partner_for_site(request)
        if not partner:
            return HttpResponseServerError('No Partner is associated with this site.')

        sku = request.GET.get('sku', None)
        if not sku:
            return HttpResponseBadRequest('No SKU provided.')

        # Make sure the SKU exists
        try:
            stock_record = StockRecord.objects.get(partner=partner, partner_sku=sku)
        except StockRecord.DoesNotExist:
            msg = 'SKU [{sku}] does not exist for partner [{name}].'.format(sku=sku, name=partner.name)
            return HttpResponseBadRequest(msg)

        # Make sure the product can be purchased
        product = stock_record.product
        purchase_info = request.strategy.fetch_for_product(product)
        if not purchase_info.availability.is_available_to_buy:
            return HttpResponseBadRequest('SKU [{}] does not exist.'.format(sku))

        self._prepare_basket(request.site, request.user, product)

        # Redirect to payment page
        url = reverse('checkout:payment')
        return HttpResponseRedirect(url, status=303)
