# pylint: disable=no-else-return


import logging
import time
from edx_rest_framework_extensions.permissions import LoginRedirectIfUnauthenticated
from oscar.apps.basket.views import *  # pylint: disable=wildcard-import, unused-wildcard-import
from oscar.apps.payment.exceptions import PaymentError
from oscar.apps.partner import strategy
from oscar.core.loading import get_class, get_model
from rest_framework.views import APIView

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.utils.html import escape
from django.utils.translation import ugettext as _

from ecommerce.extensions.analytics.utils import track_segment_event
from ecommerce.extensions.basket.constants import EMAIL_OPT_IN_ATTRIBUTE
from ecommerce.extensions.basket.exceptions import BadRequestException, RedirectException
from ecommerce.extensions.basket.utils import basket_add_organization_attribute, prepare_basket
from ecommerce.extensions.basket.views import BasketLogicMixin
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.iap.processors.android_iap import AndroidIAP
from ecommerce.extensions.iap.api.v1.serializers import OrderSerializer
from ecommerce.extensions.order.exceptions import AlreadyPlacedOrderException
from ecommerce.extensions.partner.shortcuts import get_partner_for_site

Applicator = get_class('offer.applicator', 'Applicator')
BasketAttribute = get_model('basket', 'BasketAttribute')
BasketAttributeType = get_model('basket', 'BasketAttributeType')
logger = logging.getLogger(__name__)
Product = get_model('catalogue', 'Product')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')


class MobileBasketAddItemsView(BasketLogicMixin, APIView):
    """
    View that adds multiple products to a mobile user's basket.
    """
    permission_classes = (LoginRedirectIfUnauthenticated,)

    def get(self, request):
        # Send time when this view is called - https://openedx.atlassian.net/browse/REV-984
        properties = {'emitted_at': time.time()}
        track_segment_event(request.site, request.user, 'Mobile Basket Add Items View Called', properties)

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

            return JsonResponse({'success': _('Course added to the basket successfully'), 'basket_id': basket.id}, status=200)

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


class MobileCoursePurchaseExecutionView(EdxOrderPlacementMixin, APIView):
    """
    View that adds verifies an in-app purchase and completes an order.
    """
    permission_classes = (LoginRedirectIfUnauthenticated,)

    @property
    def payment_processor(self):
        return AndroidIAP(self.request.site)

    def _get_basket(self, request, basket_id):
        """
        Retrieve a basket using a payment ID.

        Arguments:
            payment_id: payment_id received from PayPal.

        Returns:
            It will return related basket or log exception and return None if
            duplicate payment_id received or any other exception occurred.

        """
        basket = request.user.baskets.get(id=basket_id)
        basket.strategy = request.strategy

        Applicator().apply(basket, basket.owner, self.request)

        basket_add_organization_attribute(basket, self.request.GET)
        return basket

    # Disable atomicity for the view. Otherwise, we'd be unable to commit to the database
    # until the request had concluded; Django will refuse to commit when an atomic() block
    # is active, since that would break atomicity. Without an order present in the database
    # at the time fulfillment is attempted, asynchronous order fulfillment tasks will fail.
    @method_decorator(transaction.non_atomic_requests)
    def dispatch(self, request, *args, **kwargs):
        return super(MobileCoursePurchaseExecutionView, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        # Send time when this view is called - https://openedx.atlassian.net/browse/REV-984
        properties = {'emitted_at': time.time()}
        track_segment_event(request.site, request.user, 'Mobile Course Purchase View Called', properties)
        receipt = request.data
        basket_id = receipt['basket_id']
        logger.info('Payment [%s] approved by payer [%s]', receipt.get('transactionId'), request.user.id)

        try:
            basket = self._get_basket(request, basket_id)
        except ObjectDoesNotExist:
            logger.exception('Basket [%s] not found', basket_id)
            return JsonResponse({'error': 'Basket [{}] not found.'.format(basket_id)}, status=400)
        except Exception as ex:  # pylint: disable=broad-except
            logger.exception('An unexpected exception occured while obtaining basket for user [%s].', request.user.email)
            return JsonResponse({'error': 'An unexpected exception occured while obtaining basket for user {}.'.format(request.user.email)}, status=400)

        try:
            with transaction.atomic():
                try:
                    self.handle_payment(receipt, basket)
                except PaymentError:
                    return JsonResponse({'error': 'An error occured during payment handling.'}, status=400)
        except:  # pylint: disable=bare-except
            logger.exception('Attempts to handle payment for basket [%d] failed.', basket.id)
            return JsonResponse({'error': 'An error occured during handling payment.'}, status=400)

        try:
            order = self.create_order(request, basket)
        except Exception:  # pylint: disable=broad-except
            # any errors here will be logged in the create_order method. If we wanted any
            # IAP specific logging for this error, we would do that here.
            return JsonResponse({'error': 'An error occured during order creation.'}, status=400)

        try:
            self.handle_post_order(order)
        except Exception:  # pylint: disable=broad-except
            self.log_order_placement_exception(basket.order_number, basket.id)
            return JsonResponse({'error': 'An error occured during post order operations.'}, status=200)

        return JsonResponse({'order_data': OrderSerializer(order, context={'request': request}).data}, status=200)
