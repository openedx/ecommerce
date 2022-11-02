import logging
from contextlib import contextmanager
from typing import Optional

import requests
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.http import JsonResponse
from django.utils.functional import cached_property
from django.utils.translation import ugettext as _
from edx_django_utils import monitoring as monitoring_utils
from oscar.apps.partner import strategy
from oscar.apps.payment.exceptions import GatewayError, PaymentError, TransactionDeclined, UserCancelled
from oscar.core.loading import get_class, get_model
from rest_framework import permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from ecommerce.extensions.api.serializers import OrderSerializer
from ecommerce.extensions.basket.utils import (
    add_stripe_flag_to_url,
    add_utm_params_to_url,
    basket_add_organization_attribute,
    get_payment_microfrontend_or_basket_url
)
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.checkout.utils import get_receipt_page_url
from ecommerce.extensions.payment.core.sdn import checkSDN
from ecommerce.extensions.payment.exceptions import (
    AuthorizationError,
    DuplicateReferenceNumber,
    ExcessivePaymentForOrderError,
    InvalidBasketError,
    InvalidSignatureError,
    RedundantPaymentNotificationError
)
from ecommerce.extensions.payment.processors.cybersource import Cybersource, CybersourceREST
from ecommerce.extensions.payment.views import BasePaymentSubmitView

logger = logging.getLogger(__name__)

Applicator = get_class('offer.applicator', 'Applicator')
Basket = get_model('basket', 'Basket')
BasketAttribute = get_model('basket', 'BasketAttribute')
BasketAttributeType = get_model('basket', 'BasketAttributeType')
BillingAddress = get_model('order', 'BillingAddress')
BUNDLE = 'bundle_identifier'
Country = get_model('address', 'Country')
NoShippingRequired = get_class('shipping.methods', 'NoShippingRequired')
Order = get_model('order', 'Order')
OrderNumberGenerator = get_class('order.utils', 'OrderNumberGenerator')
OrderTotalCalculator = get_class('checkout.calculators', 'OrderTotalCalculator')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')


class CyberSourceProcessorMixin:
    @cached_property
    def payment_processor(self):
        return Cybersource(self.request.site)


class CybersourceOrderInitiationView:
    """
    A baseclass that includes pre-work before submitting an order to cybersource for
    payment validation.
    """

    def check_sdn(self, request, data):
        """
        Check that the supplied request and form data passes SDN checks.

        Returns:
            JsonResponse with an error if the SDN check fails, or None if it succeeds.
        """
        hit_count = checkSDN(
            request,
            data['first_name'] + ' ' + data['last_name'],
            data['city'],
            data['country'])

        if hit_count > 0:
            logger.info(
                'SDNCheck function called for basket [%d]. It received %d hit(s).',
                request.basket.id,
                hit_count,
            )
            response_to_return = {
                'error': 'There was an error submitting the basket',
                'sdn_check_failure': {'hit_count': hit_count}}

            return JsonResponse(response_to_return, status=403)

        logger.info(
            'SDNCheck function called for basket [%d]. It did not receive a hit.',
            request.basket.id,
        )
        return None


class CybersourceOrderCompletionView(EdxOrderPlacementMixin):
    """
    A baseclass that includes error handling and financial reporting for orders placed via
    CyberSource.
    """

    transaction_id: Optional[str] = None
    order_number: Optional[str] = None
    basket_id: Optional[int] = None

    def _log_cybersource_payment_failure(
            self, exception, basket, order_number, transaction_id, ppr, notification_msg=None,
            message_prefix=None, logger_function=None
    ):
        """ Logs standard payment response as exception log unless logger_function supplied. """
        message_prefix = message_prefix + ' ' if message_prefix else ''
        logger_function = logger_function if logger_function else logger.exception
        # pylint: disable=logging-not-lazy
        logger_function(
            message_prefix +
            'CyberSource payment failed due to [%s] for transaction [%s], order [%s], and basket [%d]. '
            'The complete payment response [%s] was recorded in entry [%d]. Processed by [%s].',
            exception.__class__.__name__,
            transaction_id,
            order_number,
            basket.id,
            notification_msg or "Unknown Error",
            ppr.id,
            self.payment_processor.NAME,
        )

    @contextmanager
    def log_payment_exceptions(self, basket, order_number, transaction_id, ppr, notification_msg=None):
        try:
            yield
        except (UserCancelled, TransactionDeclined, AuthorizationError) as exception:
            self._log_cybersource_payment_failure(
                exception, basket, order_number, transaction_id, ppr, notification_msg,
                logger_function=logger.info,
            )
            exception.unlogged = False
            raise
        except DuplicateReferenceNumber as exception:
            logger.info(
                'Received CyberSource payment notification for basket [%d] which is associated '
                'with existing order [%s]. No payment was collected, and no new order will be created. '
                'Processed by [%s].',
                basket.id,
                order_number,
                self.payment_processor.NAME,
            )
            exception.unlogged = False
            raise
        except RedundantPaymentNotificationError as exception:
            logger.info(
                'Received redundant CyberSource payment notification with same transaction ID for basket [%d] '
                'which is associated with an existing order [%s]. No payment was collected. Processed by [%s].',
                basket.id,
                order_number,
                self.payment_processor.NAME,
            )
            exception.unlogged = False
            raise
        except ExcessivePaymentForOrderError as exception:
            logger.info(
                'Received duplicate CyberSource payment notification with different transaction ID for basket '
                '[%d] which is associated with an existing order [%s]. Payment collected twice, request a '
                'refund. Processed by [%s].',
                basket.id,
                order_number,
                self.payment_processor.NAME,
            )
            exception.unlogged = False
            raise
        except InvalidSignatureError as exception:
            self._log_cybersource_payment_failure(
                exception, basket, order_number, transaction_id, ppr, notification_msg,
                message_prefix='CyberSource response was invalid.',
            )
            exception.unlogged = False
            raise
        except (PaymentError, Exception) as exception:
            self._log_cybersource_payment_failure(
                exception, basket, order_number, transaction_id, ppr, notification_msg,
            )
            exception.unlogged = False
            raise

    def set_payment_response_custom_metrics(
            self,
            basket_id,
            order_number,
            ppr,
            transaction_id,
            reason_code=None,
            payment_response_message=None
    ):
        reason_code = 'not-found' if reason_code is None else reason_code
        payment_response_message = 'Unknown Error' if payment_response_message is None else payment_response_message
        # IMPORTANT: Does not set metric for the entire `order_completion_message`, because it includes PII.
        #   It is accessible using the `payment_response_record_id` if needed.
        monitoring_utils.set_custom_metric('payment_response_processor_name', 'cybersource')
        monitoring_utils.set_custom_metric('payment_response_basket_id', basket_id)
        monitoring_utils.set_custom_metric('payment_response_order_number', order_number)
        monitoring_utils.set_custom_metric('payment_response_transaction_id', transaction_id)
        monitoring_utils.set_custom_metric('payment_response_record_id', ppr.id)
        monitoring_utils.set_custom_metric('payment_response_reason_code', reason_code)
        monitoring_utils.set_custom_metric('payment_response_message', payment_response_message)
        monitoring_utils.set_custom_metric('payment_response_processor', self.payment_processor.NAME)

    # Note: method has too-many-statements, but it enables tracking that all exception handling gets logged
    def validate_order_completion(self, order_completion_message):  # pylint: disable=too-many-statements
        # Note (CCB): Orders should not be created until the payment processor has validated the response's signature.
        # This validation is performed in the handle_payment method. After that method succeeds, the response can be
        # safely assumed to have originated from CyberSource.
        basket = None

        try:

            try:
                normalized_order_completion_message = self.payment_processor.normalize_processor_response(
                    order_completion_message
                )
                logger.info(
                    'Received CyberSource payment notification for transaction [%s], associated with order [%s]'
                    ' and basket [%d]. Processed by [%s].',
                    self.transaction_id,
                    self.order_number,
                    self.basket_id,
                    self.payment_processor.NAME,
                )

                basket = self._get_basket(self.basket_id)

                if not basket:
                    error_message = (
                        'Received CyberSource payment notification for non-existent '
                        'basket [%s]. Processed by [%s].' % (
                            self.basket_id,
                            self.payment_processor.NAME
                        )
                    )
                    logger.error(error_message)
                    exception = InvalidBasketError(error_message)
                    exception.unlogged = False
                    raise exception

                if basket.status != Basket.FROZEN:
                    # We don't know how serious this situation is at this point, hence
                    # the INFO level logging. This notification is most likely CyberSource
                    # telling us that they've declined an attempt to pay for an existing order.
                    logger.info(
                        'Received CyberSource payment notification for basket [%d] which is in a non-frozen state,'
                        ' [%s]. Processed by [%s].',
                        basket.id, basket.status, self.payment_processor.NAME,
                    )
            finally:
                # Store the response in the database regardless of its authenticity.
                ppr = self.payment_processor.record_processor_response(
                    self.payment_processor.serialize_order_completion(order_completion_message),
                    transaction_id=self.transaction_id,
                    basket=basket,
                )

                self.set_payment_response_custom_metrics(
                    self.basket_id,
                    self.order_number,
                    ppr,
                    self.transaction_id,
                    self.payment_processor.extract_reason_code(order_completion_message),
                    self.payment_processor.extract_payment_response_message(order_completion_message),
                )

            # Don't make this an atomic transaction; rolled back transactions prevent track_segment_event from firing.
            with self.log_payment_exceptions(
                    basket,
                    self.order_number,
                    self.transaction_id,
                    ppr,
                    self.payment_processor.extract_payment_response_message(order_completion_message)
            ):
                self.handle_payment(normalized_order_completion_message, basket)

        except Exception as exception:  # pylint: disable=bare-except
            if getattr(exception, 'unlogged', True):
                logger.exception(
                    'Unhandled exception processing CyberSource payment notification for transaction [%s], order [%s], '
                    'and basket [%d]. Processed by [%s].',
                    self.transaction_id,
                    self.order_number,
                    self.basket_id,
                    self.payment_processor.NAME,
                )
            raise

        return basket

    def _get_basket(self, basket_id):
        if not basket_id:
            return None

        try:
            basket_id = int(basket_id)
            basket = Basket.objects.get(id=basket_id)
            basket.strategy = strategy.Default()

            Applicator().apply(basket, basket.owner, self.request)
            logger.info(
                'Applicator applied, basket id: [%s]. Processed by [%s].',
                basket.id, self.payment_processor.NAME)
            return basket
        except (ValueError, ObjectDoesNotExist) as error:
            logger.warning(
                'Could not get basket--error: [%s]. Processed by [%s].',
                str(error), self.payment_processor.NAME)
            return None

    def _merge_old_basket_into_new(self):
        """
        Upon declined transaction merge old basket into new one and also copy bundle attibute
        over to new basket if any.
        """
        old_basket_id = OrderNumberGenerator().basket_id(self.order_number)
        old_basket = Basket.objects.get(id=old_basket_id)

        bundle_attributes = BasketAttribute.objects.filter(
            basket=old_basket,
            attribute_type=BasketAttributeType.objects.get(name=BUNDLE)
        )
        bundle = bundle_attributes.first().value_text if bundle_attributes.count() > 0 else None

        new_basket = Basket.objects.create(owner=old_basket.owner, site=self.request.site)

        # We intentionally avoid thawing the old basket here to prevent order
        # numbers from being reused. For more, refer to commit a1efc68.
        new_basket.merge(old_basket, add_quantities=False)
        if bundle:
            BasketAttribute.objects.update_or_create(
                basket=new_basket,
                attribute_type=BasketAttributeType.objects.get(name=BUNDLE),
                defaults={'value_text': bundle}
            )

        logger.info(
            'Created new basket [%d] from old basket [%d] for declined transaction with bundle [%s].',
            new_basket.id,
            old_basket_id,
            bundle
        )

    def complete_order(self, order_completion_message):
        try:
            basket = self.validate_order_completion(order_completion_message)
            monitoring_utils.set_custom_metric('payment_response_validation', 'success')
        except DuplicateReferenceNumber:
            # CyberSource has told us that they've declined an attempt to pay
            # for an existing order. If this happens, we can redirect the browser
            # to the receipt page for the existing order.
            monitoring_utils.set_custom_metric('payment_response_validation', 'redirect-to-receipt')
            return self.redirect_to_receipt_page()
        except TransactionDeclined:
            # Declined transactions are the most common cause of errors during payment
            # processing and tend to be easy to correct (e.g., an incorrect CVV may have
            # been provided). The recovery path is not as clear for other exceptions,
            # so we let those drop through to the payment error page.
            self._merge_old_basket_into_new()

            messages.error(self.request, _('transaction declined'), extra_tags='transaction-declined-message')

            monitoring_utils.set_custom_metric('payment_response_validation', 'redirect-to-payment-page')
            # TODO:
            # 1. There are sometimes messages from CyberSource that would make a more helpful message for users.
            # 2. We could have similar handling of other exceptions like UserCancelled and AuthorizationError

            return self.redirect_on_transaction_declined()

        except:  # pylint: disable=bare-except
            # logging handled by validate_order_completion, because not all exceptions are problematic
            monitoring_utils.set_custom_metric('payment_response_validation', 'redirect-to-error-page')
            return self.redirect_to_payment_error()

        try:
            order = self.create_order(
                self.request,
                basket,
                order_completion_message.billing_address
            )
            self.handle_post_order(order)
            return self.redirect_to_receipt_page()
        except:  # pylint: disable=bare-except
            logger.exception(
                'Error processing order for transaction [%s], with order [%s] and basket [%d]. Processed by [%s].',
                self.transaction_id,
                self.order_number,
                self.basket_id,
                self.payment_processor.NAME,
            )
            return self.redirect_to_payment_error()


class CyberSourceRESTProcessorMixin:
    @cached_property
    def payment_processor(self):
        return CybersourceREST(self.request.site)


class CybersourceAuthorizeAPIView(
        APIView,
        BasePaymentSubmitView,
        CyberSourceRESTProcessorMixin,
        CybersourceOrderCompletionView,
        CybersourceOrderInitiationView
):
    # DRF APIView wrapper which allows clients to use
    # JWT authentication when making Cybersource submit
    # requests.
    permission_classes = (permissions.IsAuthenticated,)

    data: dict

    def post(self, request):
        logger.info(
            '%s called for basket [%d]. It is in the [%s] state.',
            self.__class__.__name__,
            request.basket.id,
            request.basket.status
        )
        return super(CybersourceAuthorizeAPIView, self).post(request)

    def form_valid(self, form):
        self.data = form.cleaned_data
        basket = self.data['basket']
        request = self.request

        sdn_check_failure = self.check_sdn(request, self.data)
        if sdn_check_failure is not None:
            return sdn_check_failure

        self.basket_id = basket.id
        self.order_number = basket.order_number

        basket_add_organization_attribute(basket, self.data)

        # Freeze the basket since the user is paying for it now.
        basket.freeze()

        try:
            payment_processor_response, transaction_id = self.payment_processor.initiate_payment(
                basket,
                request,
                self.data,
            )
            self.transaction_id = transaction_id
        except GatewayError:
            return self.redirect_to_payment_error()
        else:
            return self.complete_order(payment_processor_response)

    def redirect_to_payment_error(self):
        return JsonResponse({}, status=400)

    def redirect_to_receipt_page(self):
        receipt_page_url = get_receipt_page_url(
            self.request,
            self.request.site.siteconfiguration,
            order_number=self.order_number,
            disable_back_button=True
        )
        return JsonResponse({
            'receipt_page_url': receipt_page_url,
        }, status=201)

    def redirect_on_transaction_declined(self):
        redirect_url = get_payment_microfrontend_or_basket_url(self.request)
        redirect_url = add_utm_params_to_url(redirect_url, list(self.request.GET.items()))
        redirect_url = add_stripe_flag_to_url(redirect_url, self.request)
        return JsonResponse({
            'redirectTo': redirect_url,
        }, status=400)


class ApplePayStartSessionView(CyberSourceProcessorMixin, APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        url = request.data.get('url')
        if not url:
            raise ValidationError({'error': 'url is required'})

        # The domain name sent to Apple Pay needs to match the domain name of the frontend.
        # We use a URL parameter to indicate whether the new Payment microfrontend was used to
        # make this request - since the use of the new microfrontend is request-specific - depends
        # on the state of the waffle toggle, the user's A/B test bucket, and user's toggle choice.
        #
        # As an alternative implementation, one can look at the domain of the requesting client,
        # instead of relying on this boolean URL parameter. We are going with a URL parameter since
        # it is simplest for testing at this time.
        if request.data.get('is_payment_microfrontend'):
            domain_name = request.site.siteconfiguration.payment_domain_name
        else:
            domain_name = request.site.domain

        data = {
            'merchantIdentifier': self.payment_processor.apple_pay_merchant_identifier,
            'domainName': domain_name,
            'displayName': request.site.name,
        }

        response = requests.post(url, json=data, cert=self.payment_processor.apple_pay_merchant_id_certificate_path)

        if response.status_code > 299:
            logger.warning('Failed to start Apple Pay session. [%s] returned status [%d] with content %s',
                           url, response.status_code, response.content)

        return JsonResponse(response.json(), status=response.status_code)


class CybersourceApplePayAuthorizationView(CyberSourceProcessorMixin, EdxOrderPlacementMixin, APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def _get_billing_address(self, order_completion_message):
        """ Converts ApplePayPaymentContact object to BillingAddress.

        See https://developer.apple.com/documentation/applepayjs/applepaypaymentcontact.
        """
        address_lines = order_completion_message['addressLines']
        address_line_2 = address_lines[1] if len(address_lines) > 1 else ''
        country_code = order_completion_message.get('countryCode')

        try:
            country = Country.objects.get(iso_3166_1_a2__iexact=country_code)
        except Country.DoesNotExist:
            logger.warning('Country matching code [%s] does not exist.', country_code)
            raise

        return BillingAddress(
            first_name=order_completion_message['givenName'],
            last_name=order_completion_message['familyName'],
            line1=address_lines[0],

            # Address line 2 is optional
            line2=address_line_2,

            # Oscar uses line4 for city
            line4=order_completion_message['locality'],
            # Postal code is optional
            postcode=order_completion_message.get('postalCode', ''),
            # State is optional
            state=order_completion_message.get('administrativeArea', ''),
            country=country)

    def post(self, request):
        basket = request.basket

        if not request.data.get('token'):
            raise ValidationError({'error': 'token_missing'})

        try:
            billing_address = self._get_billing_address(request.data.get('billingContact'))
        except Exception as this_exception:
            logger.exception(
                'Failed to authorize Apple Pay payment. An error occurred while parsing the billing address.')
            raise ValidationError({'error': 'billing_address_invalid'}) from this_exception

        try:
            self.handle_payment(None, basket)
        except GatewayError:
            return Response({'error': 'payment_failed'}, status=status.HTTP_502_BAD_GATEWAY)

        order = self.create_order(request, basket, billing_address=billing_address)
        return Response(OrderSerializer(order, context={'request': request}).data, status=status.HTTP_201_CREATED)

    def handle_payment(self, response, basket):
        request = self.request
        basket = request.basket
        billing_address = self._get_billing_address(request.data.get('billingContact'))
        token = request.data['token']

        handled_processor_response = self.payment_processor.request_apple_pay_authorization(
            basket, billing_address, token)
        self.record_payment(basket, handled_processor_response)
