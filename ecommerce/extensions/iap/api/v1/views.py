import logging
import time

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.utils.html import escape
from django.utils.translation import ugettext as _
from oscar.apps.basket.views import *  # pylint: disable=wildcard-import, unused-wildcard-import
from oscar.apps.payment.exceptions import PaymentError
from oscar.core.loading import get_class, get_model
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from ecommerce.extensions.analytics.utils import track_segment_event
from ecommerce.extensions.api.v2.views.checkout import CheckoutView
from ecommerce.extensions.basket.exceptions import BadRequestException
from ecommerce.extensions.basket.utils import (
    basket_add_organization_attribute,
    prepare_basket,
    set_email_preference_on_basket
)
from ecommerce.extensions.basket.views import BasketLogicMixin
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.iap.api.v1.constants import (
    COURSE_ADDED_TO_BASKET,
    COURSE_ALREADY_PAID_ON_DEVICE,
    ERROR_ALREADY_PURCHASED,
    ERROR_BASKET_ID_NOT_PROVIDED,
    ERROR_BASKET_NOT_FOUND,
    ERROR_DURING_ORDER_CREATION,
    ERROR_DURING_PAYMENT_HANDLING,
    ERROR_DURING_POST_ORDER_OP,
    ERROR_WHILE_OBTAINING_BASKET_FOR_USER,
    LOGGER_BASKET_NOT_FOUND,
    LOGGER_PAYMENT_APPROVED,
    LOGGER_PAYMENT_FAILED_FOR_BASKET,
    LOGGER_STARTING_PAYMENT_FLOW,
    NO_PRODUCT_AVAILABLE,
    PRODUCT_IS_NOT_AVAILABLE,
    PRODUCTS_DO_NOT_EXIST,
    SEGMENT_MOBILE_BASKET_ADD,
    SEGMENT_MOBILE_PURCHASE_VIEW
)
from ecommerce.extensions.iap.api.v1.serializers import MobileOrderSerializer
from ecommerce.extensions.iap.processors.android_iap import AndroidIAP
from ecommerce.extensions.iap.processors.ios_iap import IOSIAP
from ecommerce.extensions.order.exceptions import AlreadyPlacedOrderException
from ecommerce.extensions.partner.shortcuts import get_partner_for_site
from ecommerce.extensions.payment.exceptions import RedundantPaymentNotificationError

Applicator = get_class('offer.applicator', 'Applicator')
BasketAttribute = get_model('basket', 'BasketAttribute')
BasketAttributeType = get_model('basket', 'BasketAttributeType')
logger = logging.getLogger(__name__)
Product = get_model('catalogue', 'Product')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')


class MobileBasketAddItemsView(BasketLogicMixin, APIView):
    """
    View that adds single or multiple products to a mobile user's basket.
    """
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        # Send time when this view is called - https://openedx.atlassian.net/browse/REV-984
        track_segment_event(request.site, request.user, SEGMENT_MOBILE_BASKET_ADD, {'emitted_at': time.time()})

        try:
            skus = self._get_skus(request)
            products = self._get_products(request, skus)

            logger.info(LOGGER_STARTING_PAYMENT_FLOW, request.user.username, skus)

            available_products = self._get_available_products(request, products)

            try:
                basket = prepare_basket(request, available_products)
            except AlreadyPlacedOrderException:
                return JsonResponse({'error': _(ERROR_ALREADY_PURCHASED)}, status=406)

            set_email_preference_on_basket(request, basket)

            return JsonResponse({'success': _(COURSE_ADDED_TO_BASKET), 'basket_id': basket.id},
                                status=200)

        except BadRequestException as e:
            return JsonResponse({'error': str(e)}, status=400)

    def _get_skus(self, request):
        skus = [escape(sku) for sku in request.GET.getlist('sku')]
        if not skus:
            raise BadRequestException(_('No SKUs provided.'))

        return skus

    def _get_products(self, request, skus):
        partner = get_partner_for_site(request)
        products = Product.objects.filter(stockrecords__partner=partner, stockrecords__partner_sku__in=skus)
        if not products:
            raise BadRequestException(_(PRODUCTS_DO_NOT_EXIST).format(skus=', '.join(skus)))

        return products

    def _get_available_products(self, request, products):
        unavailable_product_ids = []

        for product in products:
            purchase_info = request.strategy.fetch_for_product(product)
            if not purchase_info.availability.is_available_to_buy:
                logger.warning(PRODUCT_IS_NOT_AVAILABLE, product.title)
                unavailable_product_ids.append(product.id)

        available_products = products.exclude(id__in=unavailable_product_ids)
        if not available_products:
            raise BadRequestException(_(NO_PRODUCT_AVAILABLE))

        return available_products


class MobileCoursePurchaseExecutionView(EdxOrderPlacementMixin, APIView):
    """
    View that verifies an in-app purchase and completes an order for a user.
    """
    permission_classes = (IsAuthenticated,)

    @property
    def payment_processor(self):
        if self.request.data['payment_processor'] == IOSIAP.NAME:
            return IOSIAP(self.request.site)

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

    def post(self, request):
        # Send time when this view is called - https://openedx.atlassian.net/browse/REV-984
        track_segment_event(request.site, request.user, SEGMENT_MOBILE_PURCHASE_VIEW, {'emitted_at': time.time()})
        receipt = request.data

        basket_id = receipt.get('basket_id')
        if not basket_id:
            return JsonResponse({'error': ERROR_BASKET_ID_NOT_PROVIDED}, status=400)
        logger.info(LOGGER_PAYMENT_APPROVED, receipt.get('transactionId'), request.user.id)

        try:
            basket = self._get_basket(request, basket_id)
        except ObjectDoesNotExist:
            logger.exception(LOGGER_BASKET_NOT_FOUND, basket_id)
            return JsonResponse({'error': ERROR_BASKET_NOT_FOUND.format(basket_id)}, status=400)
        except:  # pylint: disable=bare-except
            error_message = ERROR_WHILE_OBTAINING_BASKET_FOR_USER.format(request.user.email)
            logger.exception(error_message)
            return JsonResponse({'error': error_message}, status=400)

        try:
            with transaction.atomic():
                try:
                    self.handle_payment(receipt, basket)
                except RedundantPaymentNotificationError:
                    return JsonResponse({'error': COURSE_ALREADY_PAID_ON_DEVICE}, status=409)
                except PaymentError:
                    return JsonResponse({'error': ERROR_DURING_PAYMENT_HANDLING}, status=400)
        except:  # pylint: disable=bare-except
            logger.exception(LOGGER_PAYMENT_FAILED_FOR_BASKET, basket.id)
            return JsonResponse({'error': ERROR_DURING_PAYMENT_HANDLING}, status=400)

        try:
            order = self.create_order(request, basket)
        except Exception:  # pylint: disable=broad-except
            # Any errors here will be logged in the create_order method. If we wanted any
            # IAP specific logging for this error, we would do that here.
            return JsonResponse({'error': ERROR_DURING_ORDER_CREATION}, status=400)

        try:
            self.handle_post_order(order)
        except Exception:  # pylint: disable=broad-except
            self.log_order_placement_exception(basket.order_number, basket.id)
            return JsonResponse({'error': ERROR_DURING_POST_ORDER_OP}, status=200)

        return JsonResponse({'order_data': MobileOrderSerializer(order, context={'request': request}).data}, status=200)


class MobileCheckoutView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        response = CheckoutView.as_view()(request._request)  # pylint: disable=W0212
        if response.status_code != 200:
            return JsonResponse({'error': response.content.decode()}, status=response.status_code)

        return response
