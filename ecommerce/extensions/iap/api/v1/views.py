# pylint: disable=no-else-return


import logging
import time
from django.http import JsonResponse
from django.utils.html import escape
from django.utils.translation import ugettext as _
from edx_rest_framework_extensions.permissions import LoginRedirectIfUnauthenticated
from oscar.apps.basket.views import *  # pylint: disable=wildcard-import, unused-wildcard-import
from rest_framework.views import APIView
from ecommerce.extensions.analytics.utils import track_segment_event
from ecommerce.extensions.basket.constants import EMAIL_OPT_IN_ATTRIBUTE
from ecommerce.extensions.basket.exceptions import BadRequestException, RedirectException
from ecommerce.extensions.basket.utils import prepare_basket
from ecommerce.extensions.basket.views import BasketLogicMixin
from ecommerce.extensions.order.exceptions import AlreadyPlacedOrderException
from ecommerce.extensions.partner.shortcuts import get_partner_for_site

BasketAttribute = get_model('basket', 'BasketAttribute')
BasketAttributeType = get_model('basket', 'BasketAttributeType')
logger = logging.getLogger(__name__)
Product = get_model('catalogue', 'Product')
Voucher = get_model('voucher', 'Voucher')


class MobileBasketAddItemsView(BasketLogicMixin, APIView):
    """
    View that adds multiple products to a mobile user's basket.
    """
    permission_classes = (LoginRedirectIfUnauthenticated,)

    def get(self, request):
        # Send time when this view is called - https://openedx.atlassian.net/browse/REV-984
        properties = {'emitted_at': time.time()}
        track_segment_event(request.site, request.user, 'Basket Add Items View Called', properties)

        try:
            skus = self._get_skus(request)
            products = self._get_products(request, skus)

            logger.info('Starting payment flow for user [%s] for products [%s].', request.user.username, skus)

            available_products = self._get_available_products(request, products)

            try:
                basket = prepare_basket(request, available_products)
            except AlreadyPlacedOrderException:
                return JsonResponse({'error': _('You have already purchased these products')}, status=406)

            self._set_email_preference_on_basket(request, basket)

            return JsonResponse({'success': _('Course added to the basket successfully')}, status=200)

        except BadRequestException as e:
            return JsonResponse({'error': str(e)}, status=400)
        except RedirectException as e:
            return e.response

    def _get_skus(self, request):
        skus = [escape(sku) for sku in request.GET.getlist('sku')]
        if not skus:
            raise BadRequestException(_('No SKUs provided.'))
        return skus

    def _get_products(self, request, skus):
        partner = get_partner_for_site(request)
        products = Product.objects.filter(stockrecords__partner=partner, stockrecords__partner_sku__in=skus)
        if not products:
            raise BadRequestException(_('Products with SKU(s) [{skus}] do not exist.').format(skus=', '.join(skus)))
        return products

    def _get_available_products(self, request, products):
        unavailable_product_ids = []
        for product in products:
            purchase_info = request.strategy.fetch_for_product(product)
            if not purchase_info.availability.is_available_to_buy:
                logger.warning('Product [%s] is not available to buy.', product.title)
                unavailable_product_ids.append(product.id)

        available_products = products.exclude(id__in=unavailable_product_ids)
        if not available_products:
            raise BadRequestException(_('No product is available to buy.'))
        return available_products

    def _set_email_preference_on_basket(self, request, basket):
        """
        Associate the user's email opt in preferences with the basket in
        order to opt them in later as part of fulfillment
        """
        BasketAttribute.objects.update_or_create(
            basket=basket,
            attribute_type=BasketAttributeType.objects.get(name=EMAIL_OPT_IN_ATTRIBUTE),
            defaults={'value_text': request.GET.get('email_opt_in') == 'true'},
        )
