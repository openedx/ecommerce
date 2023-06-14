import datetime
import logging
import time

import app_store_notifications_v2_validator as asn2
import httplib2
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.utils.html import escape
from django.utils.translation import ugettext as _
from edx_django_utils import monitoring as monitoring_utils
from edx_rest_framework_extensions.permissions import LoginRedirectIfUnauthenticated
from googleapiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials
from oscar.apps.basket.views import *  # pylint: disable=wildcard-import, unused-wildcard-import
from oscar.apps.payment.exceptions import GatewayError, PaymentError
from oscar.core.loading import get_class, get_model
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
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
    ERROR_ORDER_NOT_FOUND_FOR_REFUND,
    ERROR_REFUND_NOT_COMPLETED,
    ERROR_TRANSACTION_NOT_FOUND_FOR_REFUND,
    GOOGLE_PUBLISHER_API_SCOPE,
    IGNORE_NON_REFUND_NOTIFICATION_FROM_APPLE,
    LOGGER_BASKET_ALREADY_PURCHASED,
    LOGGER_BASKET_CREATED,
    LOGGER_BASKET_CREATION_FAILED,
    LOGGER_BASKET_NOT_FOUND,
    LOGGER_EXECUTE_ALREADY_PURCHASED,
    LOGGER_EXECUTE_GATEWAY_ERROR,
    LOGGER_EXECUTE_ORDER_CREATION_FAILED,
    LOGGER_EXECUTE_PAYMENT_ERROR,
    LOGGER_EXECUTE_REDUNDANT_PAYMENT,
    LOGGER_EXECUTE_STARTED,
    LOGGER_EXECUTE_SUCCESSFUL,
    LOGGER_PAYMENT_FAILED_FOR_BASKET,
    LOGGER_REFUND_SUCCESSFUL,
    LOGGER_STARTING_PAYMENT_FLOW,
    NO_PRODUCT_AVAILABLE,
    PRODUCT_IS_NOT_AVAILABLE,
    PRODUCTS_DO_NOT_EXIST,
    RECEIVED_NOTIFICATION_FROM_APPLE,
    SEGMENT_MOBILE_BASKET_ADD,
    SEGMENT_MOBILE_PURCHASE_VIEW
)
from ecommerce.extensions.iap.api.v1.exceptions import RefundCompletionException
from ecommerce.extensions.iap.api.v1.serializers import MobileOrderSerializer
from ecommerce.extensions.iap.api.v1.utils import products_in_basket_already_purchased
from ecommerce.extensions.iap.models import IAPProcessorConfiguration
from ecommerce.extensions.iap.processors.android_iap import AndroidIAP
from ecommerce.extensions.iap.processors.ios_iap import IOSIAP
from ecommerce.extensions.order.exceptions import AlreadyPlacedOrderException
from ecommerce.extensions.partner.shortcuts import get_partner_for_site
from ecommerce.extensions.payment.exceptions import RedundantPaymentNotificationError
from ecommerce.extensions.refund.api import create_refunds, find_orders_associated_with_course
from ecommerce.extensions.refund.status import REFUND

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
    permission_classes = (LoginRedirectIfUnauthenticated,)

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
                logger.exception(LOGGER_BASKET_ALREADY_PURCHASED, request.user.username, skus)
                return JsonResponse({'error': _(ERROR_ALREADY_PURCHASED)}, status=status.HTTP_406_NOT_ACCEPTABLE)

            set_email_preference_on_basket(request, basket)

            logger.info(LOGGER_BASKET_CREATED, request.user.username, skus)

            return JsonResponse({'success': _(COURSE_ADDED_TO_BASKET), 'basket_id': basket.id},
                                status=status.HTTP_200_OK)

        except BadRequestException as exc:
            logger.exception(LOGGER_BASKET_CREATION_FAILED, request.user.username, str(exc))
            return JsonResponse({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

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


class MobileCheckoutView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        # TODO: Add check for products_in_basket_already_purchased
        # TODO: Add logging for api/user_info after reading from request obj
        response = CheckoutView.as_view()(request._request)  # pylint: disable=W0212
        if response.status_code != 200:
            return JsonResponse({'error': response.content.decode()}, status=response.status_code)

        return response


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
        Retrieve a basket using a basket ID.
        Arguments:
            basket_id: basket_id representing basket.
        Returns:
            It will return related basket or raise AlreadyPlacedOrderException
            if products in basket have already been purchased.
        """
        basket = request.user.baskets.get(id=basket_id)
        basket.strategy = request.strategy

        Applicator().apply(basket, basket.owner, self.request)
        basket_add_organization_attribute(basket, self.request.GET)

        if products_in_basket_already_purchased(request.user, basket, request.site):
            raise AlreadyPlacedOrderException

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
        logger.info(LOGGER_EXECUTE_STARTED, request.user.username, basket_id, self.payment_processor.NAME)

        try:
            basket = self._get_basket(request, basket_id)
        except ObjectDoesNotExist:
            logger.exception(LOGGER_BASKET_NOT_FOUND, basket_id, request.user.username)
            return JsonResponse({'error': ERROR_BASKET_NOT_FOUND.format(basket_id)}, status=400)
        except AlreadyPlacedOrderException:
            logger.exception(LOGGER_EXECUTE_ALREADY_PURCHASED, request.user.username, basket_id)
            return JsonResponse({'error': _(ERROR_ALREADY_PURCHASED)}, status=406)

        with transaction.atomic():
            try:
                self.handle_payment(receipt, basket)
            except GatewayError as exception:
                logger.exception(LOGGER_EXECUTE_GATEWAY_ERROR, request.user.username, basket_id, str(exception))
                return JsonResponse({'error': ERROR_DURING_PAYMENT_HANDLING}, status=400)
            except KeyError as exception:
                logger.exception(LOGGER_PAYMENT_FAILED_FOR_BASKET, basket_id, str(exception))
                return JsonResponse({'error': ERROR_DURING_PAYMENT_HANDLING}, status=400)
            except RedundantPaymentNotificationError:
                logger.exception(LOGGER_EXECUTE_REDUNDANT_PAYMENT, request.user.username, basket_id)
                return JsonResponse({'error': COURSE_ALREADY_PAID_ON_DEVICE}, status=409)
            except PaymentError as exception:
                logger.exception(LOGGER_EXECUTE_PAYMENT_ERROR, request.user.username, basket_id, str(exception))
                return JsonResponse({'error': ERROR_DURING_PAYMENT_HANDLING}, status=400)

        try:
            order = self.create_order(request, basket)
        except Exception as exception:  # pylint: disable=broad-except
            logger.exception(LOGGER_EXECUTE_ORDER_CREATION_FAILED, request.user.username, basket_id, str(exception))
            return JsonResponse({'error': ERROR_DURING_ORDER_CREATION}, status=400)

        try:
            self.handle_post_order(order)
        except AttributeError:
            self.log_order_placement_exception(basket.order_number, basket.id)
            return JsonResponse({'error': ERROR_DURING_POST_ORDER_OP}, status=200)

        logger.info(LOGGER_EXECUTE_SUCCESSFUL, request.user.username, basket_id, self.payment_processor.NAME)
        return JsonResponse({'order_data': MobileOrderSerializer(order, context={'request': request}).data}, status=200)


class BaseRefund(APIView):
    """ Base refund class for iOS and Android refunds """
    authentication_classes = ()

    def refund(self, transaction_id, processor_response):
        """ Get a transaction id and create a refund against that transaction. """
        is_refunded = False
        original_purchase = PaymentProcessorResponse.objects.filter(transaction_id=transaction_id,
                                                                    processor_name=self.processor_name).first()
        if not original_purchase:
            logger.error(ERROR_TRANSACTION_NOT_FOUND_FOR_REFUND, transaction_id, self.processor_name)
            return is_refunded

        basket = original_purchase.basket
        user = basket.owner
        course_key = basket.all_lines().first().product.attr.course_key
        orders = find_orders_associated_with_course(user, course_key)
        try:
            with transaction.atomic():
                refunds = create_refunds(orders, course_key)
                if not refunds:
                    monitoring_utils.set_custom_attribute('iap_no_order_to_refund', transaction_id)
                    logger.error(ERROR_ORDER_NOT_FOUND_FOR_REFUND, transaction_id, self.processor_name)
                    return is_refunded

                refund = refunds[0]
                refund.approve(revoke_fulfillment=True)
                if refund.status != REFUND.COMPLETE:
                    monitoring_utils.set_custom_attribute('iap_unrefunded_order', transaction_id)
                    raise RefundCompletionException

                PaymentProcessorResponse.objects.create(processor_name=self.processor_name,
                                                        transaction_id=transaction_id,
                                                        response=processor_response, basket=basket)
                logger.info(LOGGER_REFUND_SUCCESSFUL, transaction_id, self.processor_name)
                is_refunded = True

        except RefundCompletionException:
            logger.exception(ERROR_REFUND_NOT_COMPLETED, user.username, course_key, self.processor_name)

        return is_refunded


class AndroidRefundView(BaseRefund):
    """
    Create refunds for orders refunded by google and un-enroll users from relevant courses
    """
    processor_name = AndroidIAP.NAME
    timeout = 30

    def get(self, request):
        """
        Get all refunds in last 3 days from voidedpurchases api
        and call refund method on every refund.
        """

        partner_short_code = request.site.siteconfiguration.partner.short_code
        configuration = settings.PAYMENT_PROCESSOR_CONFIG[partner_short_code.lower()][self.processor_name.lower()]
        service = self._get_service(configuration)

        refunds_age = IAPProcessorConfiguration.get_solo().android_refunds_age_in_days
        refunds_time = datetime.datetime.now() - datetime.timedelta(days=refunds_age)
        refunds_time_in_ms = round(refunds_time.timestamp() * 1000)
        refund_list = service.purchases().voidedpurchases()
        refunds = refund_list.list(packageName=configuration['google_bundle_id'],
                                   startTime=refunds_time_in_ms).execute()
        for refund in refunds.get('voidedPurchases', []):
            self.refund(refund['orderId'], refund)

        return Response()

    def _get_service(self, configuration):
        """ Create a service to interact with google api. """
        play_console_credentials = configuration.get('google_service_account_key_file')
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(play_console_credentials,
                                                                       GOOGLE_PUBLISHER_API_SCOPE)
        http = httplib2.Http(timeout=self.timeout)
        http = credentials.authorize(http)

        service = build("androidpublisher", "v3", http=http)
        return service


class IOSRefundView(BaseRefund):
    processor_name = IOSIAP.NAME

    def post(self, request):
        """
        This endpoint is registered as a callback for every refund made in Appstore.
        It receives refund data and un enrolls user from the related course.
        If we don't send back 200 response to the Appstore, it will retry this url multiple times.
        """
        is_refunded = False
        try:
            apple_cert_file_path = "ecommerce/extensions/iap/api/v1/AppleRootCA-G3.cer"
            refund_data = asn2.parse(request.body, apple_root_cert_path=apple_cert_file_path)
            logger.info(RECEIVED_NOTIFICATION_FROM_APPLE, refund_data['notificationType'])
            if refund_data['notificationType'] == 'REFUND':
                original_transaction_id = refund_data['data']['signedTransactionInfo']['originalTransactionId']
                is_refunded = self.refund(original_transaction_id, refund_data)
            else:
                logger.info(IGNORE_NON_REFUND_NOTIFICATION_FROM_APPLE)
                return Response(status=status.HTTP_200_OK)

        except Exception:  # pylint: disable=broad-except
            pass

        status_code = status.HTTP_200_OK if is_refunded else status.HTTP_500_INTERNAL_SERVER_ERROR
        return Response(status=status_code)
