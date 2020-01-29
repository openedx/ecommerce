from __future__ import absolute_import, unicode_literals

import logging

import requests
import six
import waffle
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.translation import ugettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View
from edx_django_utils import monitoring as monitoring_utils
from edx_rest_api_client.client import EdxRestApiClient
from edx_rest_api_client.exceptions import SlumberHttpBaseException
from oscar.apps.partner import strategy
from oscar.apps.payment.exceptions import GatewayError, PaymentError, TransactionDeclined, UserCancelled
from oscar.core.loading import get_class, get_model
from rest_framework import permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from ecommerce.core.url_utils import absolute_redirect, get_lms_url
from ecommerce.extensions.api.serializers import OrderSerializer
from ecommerce.extensions.basket.utils import (
    basket_add_organization_attribute,
    get_payment_microfrontend_or_basket_url
)
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.checkout.utils import get_receipt_page_url
from ecommerce.extensions.offer.constants import DYNAMIC_DISCOUNT_FLAG
from ecommerce.extensions.payment.exceptions import (
    AuthorizationError,
    DuplicateReferenceNumber,
    ExcessivePaymentForOrderError,
    InvalidBasketError,
    InvalidSignatureError,
    RedundantPaymentNotificationError
)
from ecommerce.extensions.payment.processors.cybersource import Cybersource
from ecommerce.extensions.payment.utils import clean_field_value
from ecommerce.extensions.payment.views import BasePaymentSubmitView

logger = logging.getLogger(__name__)

Applicator = get_class('offer.applicator', 'Applicator')
Basket = get_model('basket', 'Basket')
BillingAddress = get_model('order', 'BillingAddress')
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


class CybersourceSubmitView(BasePaymentSubmitView):
    """ Starts CyberSource payment process.

    This view is intended to be called asynchronously by the payment form. The view expects POST data containing a
    `Basket` ID. The specified basket is frozen, and CyberSource parameters are returned as a JSON object.
    """
    FIELD_MAPPINGS = {
        'city': 'bill_to_address_city',
        'country': 'bill_to_address_country',
        'address_line1': 'bill_to_address_line1',
        'address_line2': 'bill_to_address_line2',
        'postal_code': 'bill_to_address_postal_code',
        'state': 'bill_to_address_state',
        'first_name': 'bill_to_forename',
        'last_name': 'bill_to_surname',
    }

    def form_valid(self, form):
        data = form.cleaned_data
        basket = data['basket']
        request = self.request
        user = request.user

        # Add extra parameters for Silent Order POST
        extra_parameters = {
            'payment_method': 'card',
            'unsigned_field_names': ','.join(Cybersource.PCI_FIELDS),
            'bill_to_email': user.email,
            # Fall back to order number when there is no session key (JWT auth)
            'device_fingerprint_id': request.session.session_key or basket.order_number,
        }

        for source, destination in six.iteritems(self.FIELD_MAPPINGS):
            extra_parameters[destination] = clean_field_value(data[source])

        parameters = Cybersource(self.request.site).get_transaction_parameters(
            basket,
            use_client_side_checkout=True,
            extra_parameters=extra_parameters
        )

        logger.info(
            'Parameters signed for CyberSource transaction [%s], associated with basket [%d].',
            # TODO: transaction_id is None in logs. This should be fixed.
            parameters.get('transaction_id'),
            basket.id
        )

        # This parameter is only used by the Web/Mobile flow. It is not needed for for Silent Order POST.
        parameters.pop('payment_page_url', None)

        # Ensure that the response can be properly rendered so that we
        # don't have to deal with thawing the basket in the event of an error.
        response = JsonResponse({'form_fields': parameters})

        basket_add_organization_attribute(basket, data)

        # Freeze the basket since the user is paying for it now.
        basket.freeze()

        return response


class CybersourceSubmitAPIView(APIView, CybersourceSubmitView):
    # DRF APIView wrapper which allows clients to use
    # JWT authentication when making Cybersource submit
    # requests.
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        logger.info(
            '%s called for basket [%d]. It is in the [%s] state.',
            self.__class__.__name__,
            request.basket.id,
            request.basket.status
        )
        return super(CybersourceSubmitAPIView, self).post(request)


class CybersourceInterstitialView(CyberSourceProcessorMixin, EdxOrderPlacementMixin, View):
    """
    Interstitial view for Cybersource Payments.

    Side effect:
        Sets the custom metric ``payment_response_validation`` to one of the following:
            'success', 'redirect-to-receipt', 'redirect-to-payment-page', 'redirect-to-error-page'

    """

    # Disable atomicity for the view. Otherwise, we'd be unable to commit to the database
    # until the request had concluded; Django will refuse to commit when an atomic() block
    # is active, since that would break atomicity. Without an order present in the database
    # at the time fulfillment is attempted, asynchronous order fulfillment tasks will fail.
    @method_decorator(transaction.non_atomic_requests)
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super(CybersourceInterstitialView, self).dispatch(request, *args, **kwargs)

    def _get_billing_address(self, cybersource_response):
        field = 'req_bill_to_address_line1'
        # Address line 1 is optional if flag is enabled
        line1 = (cybersource_response.get(field, '')
                 if waffle.switch_is_active('optional_location_fields')
                 else cybersource_response[field])
        return BillingAddress(
            first_name=cybersource_response['req_bill_to_forename'],
            last_name=cybersource_response['req_bill_to_surname'],
            line1=line1,

            # Address line 2 is optional
            line2=cybersource_response.get('req_bill_to_address_line2', ''),

            # Oscar uses line4 for city
            line4=cybersource_response['req_bill_to_address_city'],
            # Postal code is optional
            postcode=cybersource_response.get('req_bill_to_address_postal_code', ''),
            # State is optional
            state=cybersource_response.get('req_bill_to_address_state', ''),
            country=Country.objects.get(
                iso_3166_1_a2=cybersource_response['req_bill_to_address_country']))

    def _add_dynamic_discount_to_request(self, basket):
        # TODO: Remove as a part of REVMI-124 as this is a hacky solution
        # The problem is that orders are being created after payment processing, and the discount is not
        # saved in the database, so it needs to be calculated again in order to save the correct info to the
        # order. REVMI-124 will create the order before payment processing, when we have the discount context.
        if waffle.flag_is_active(self.request, DYNAMIC_DISCOUNT_FLAG) and basket.lines.count() == 1:  # pragma: no cover  pylint: disable=line-too-long
            discount_lms_url = get_lms_url('/api/discounts/')
            lms_discount_client = EdxRestApiClient(discount_lms_url,
                                                   jwt=self.request.site.siteconfiguration.access_token)
            ck = basket.lines.first().product.course_id
            user_id = basket.owner.lms_user_id
            try:
                response = lms_discount_client.user(user_id).course(ck).get()
                self.request.POST = self.request.POST.copy()
                self.request.POST['discount_jwt'] = response.get('jwt')
                logger.info(
                    """Received discount jwt from LMS with
                    url: [%s],
                    user_id: [%s],
                    course_id: [%s],
                    and basket_id: [%s]
                    returned [%s]""",
                    discount_lms_url,
                    str(user_id),
                    ck,
                    basket.id,
                    response)
            except (SlumberHttpBaseException, requests.exceptions.Timeout) as error:
                logger.warning(
                    """Failed to receive discount jwt from LMS with
                    url: [%s],
                    user_id: [%s],
                    course_id: [%s],
                    and basket_id: [%s]
                    returned [%s]""",
                    discount_lms_url,
                    str(user_id),
                    ck,
                    basket.id,
                    vars(error.response) if hasattr(error, 'response') else '')
            # End TODO

    def _get_basket(self, basket_id):
        if not basket_id:
            return None

        try:
            basket_id = int(basket_id)
            basket = Basket.objects.get(id=basket_id)
            basket.strategy = strategy.Default()

            # TODO: Remove as a part of REVMI-124 as this is a hacky solution
            # The problem is that orders are being created after payment processing, and the discount is not
            # saved in the database, so it needs to be calculated again in order to save the correct info to the
            # order. REVMI-124 will create the order before payment processing, when we have the discount context.
            self._add_dynamic_discount_to_request(basket)
            # End TODO

            Applicator().apply(basket, basket.owner, self.request)
            logger.info(
                'Applicator applied, basket id: [%s]',
                basket.id)
            return basket
        except (ValueError, ObjectDoesNotExist) as error:
            logger.warning(
                'Could not get basket--error: [%s]',
                str(error))
            return None

    def get_ids_from_notification(self, notification):
        transaction_id = notification.get('transaction_id')
        order_number = notification.get('req_reference_number')
        try:
            basket_id = OrderNumberGenerator().basket_id(order_number)
        except:  # pylint: disable=bare-except
            logger.exception(
                'Error generating basket_id from CyberSource notification with transaction [%s] and order [%s].',
                transaction_id,
                order_number,
            )
        return (transaction_id, order_number, basket_id)

    # Note: method has too-many-statements, but it enables tracking that all exception handling gets logged
    def validate_notification(self, notification):  # pylint: disable=too-many-statements
        # Note (CCB): Orders should not be created until the payment processor has validated the response's signature.
        # This validation is performed in the handle_payment method. After that method succeeds, the response can be
        # safely assumed to have originated from CyberSource.
        basket = None
        transaction_id = None
        notification = notification or {}
        unhandled_exception_logging = True

        try:

            try:
                transaction_id, order_number, basket_id = self.get_ids_from_notification(notification)

                logger.info(
                    'Received CyberSource payment notification for transaction [%s], associated with order [%s]'
                    ' and basket [%d].',
                    transaction_id,
                    order_number,
                    basket_id
                )

                basket = self._get_basket(basket_id)

                if not basket:
                    error_message = (
                        'Received CyberSource payment notification for non-existent basket [%s].' % basket_id
                    )
                    logger.error(error_message)
                    unhandled_exception_logging = False
                    raise InvalidBasketError(error_message)

                if basket.status != Basket.FROZEN:
                    # We don't know how serious this situation is at this point, hence
                    # the INFO level logging. This notification is most likely CyberSource
                    # telling us that they've declined an attempt to pay for an existing order.
                    logger.info(
                        'Received CyberSource payment notification for basket [%d] which is in a non-frozen state,'
                        ' [%s]',
                        basket.id, basket.status
                    )
            finally:
                # Store the response in the database regardless of its authenticity.
                ppr = self.payment_processor.record_processor_response(
                    notification, transaction_id=transaction_id, basket=basket
                )
                self._set_payment_response_custom_metrics(basket, notification, order_number, ppr, transaction_id)

            # Explicitly delimit operations which will be rolled back if an exception occurs.
            with transaction.atomic():
                try:
                    self.handle_payment(notification, basket)
                except (UserCancelled, TransactionDeclined, AuthorizationError) as exception:
                    self._log_cybersource_payment_failure(
                        exception, basket, order_number, transaction_id, notification, ppr,
                        logger_function=logger.info,
                    )
                    unhandled_exception_logging = False
                    raise
                except DuplicateReferenceNumber:
                    logger.info(
                        'Received CyberSource payment notification for basket [%d] which is associated '
                        'with existing order [%s]. No payment was collected, and no new order will be created.',
                        basket.id,
                        order_number
                    )
                    unhandled_exception_logging = False
                    raise
                except RedundantPaymentNotificationError:
                    logger.info(
                        'Received redundant CyberSource payment notification with same transaction ID for basket [%d] '
                        'which is associated with an existing order [%s]. No payment was collected.',
                        basket.id,
                        order_number
                    )
                    unhandled_exception_logging = False
                    raise
                except ExcessivePaymentForOrderError:
                    logger.info(
                        'Received duplicate CyberSource payment notification with different transaction ID for basket '
                        '[%d] which is associated with an existing order [%s]. Payment collected twice, request a '
                        'refund.',
                        basket.id,
                        order_number
                    )
                    unhandled_exception_logging = False
                    raise
                except InvalidSignatureError as exception:
                    self._log_cybersource_payment_failure(
                        exception, basket, order_number, transaction_id, notification, ppr,
                        message_prefix='CyberSource response was invalid.',
                    )
                    unhandled_exception_logging = False
                    raise
                except (PaymentError, Exception) as exception:
                    self._log_cybersource_payment_failure(
                        exception, basket, order_number, transaction_id, notification, ppr,
                    )
                    unhandled_exception_logging = False
                    raise

        except:  # pylint: disable=bare-except
            if unhandled_exception_logging:
                logger.exception(
                    'Unhandled exception processing CyberSource payment notification for transaction [%s], order [%s], '
                    'and basket [%d].',
                    transaction_id,
                    order_number,
                    basket_id
                )
            raise

        return basket

    def _set_payment_response_custom_metrics(self, basket, notification, order_number, ppr, transaction_id):
        # IMPORTANT: Do not set metric for the entire `notification`, because it includes PII.
        #   It is accessible using the `payment_response_record_id` if needed.
        monitoring_utils.set_custom_metric('payment_response_processor_name', 'cybersource')
        monitoring_utils.set_custom_metric('payment_response_basket_id', basket.id)
        monitoring_utils.set_custom_metric('payment_response_order_number', order_number)
        monitoring_utils.set_custom_metric('payment_response_transaction_id', transaction_id)
        monitoring_utils.set_custom_metric('payment_response_record_id', ppr.id)
        # For reason_code, see https://support.cybersource.com/s/article/What-does-this-response-code-mean#code_table
        reason_code = notification.get("reason_code", "not-found")
        monitoring_utils.set_custom_metric('payment_response_reason_code', reason_code)
        payment_response_message = notification.get("message", 'Unknown Error')
        monitoring_utils.set_custom_metric('payment_response_message', payment_response_message)

    def _log_cybersource_payment_failure(
            self, exception, basket, order_number, transaction_id, notification, ppr,
            message_prefix=None, logger_function=None
    ):
        """ Logs standard payment response as exception log unless logger_function supplied. """
        message_prefix = message_prefix + ' ' if message_prefix else ''
        logger_function = logger_function if logger_function else logger.exception
        # pylint: disable=logging-not-lazy
        logger_function(
            message_prefix +
            'CyberSource payment failed due to [%s] for transaction [%s], order [%s], and basket [%d]. '
            'The complete payment response [%s] was recorded in entry [%d].',
            exception.__class__.__name__,
            transaction_id,
            order_number,
            basket.id,
            notification.get("message", "Unknown Error"),
            ppr.id
        )

    def post(self, request, *args, **kwargs):  # pylint: disable=unused-argument
        """Process a CyberSource merchant notification and place an order for paid products as appropriate."""
        notification = request.POST.dict()
        try:
            basket = self.validate_notification(notification)
            monitoring_utils.set_custom_metric('payment_response_validation', 'success')
        except DuplicateReferenceNumber:
            # CyberSource has told us that they've declined an attempt to pay
            # for an existing order. If this happens, we can redirect the browser
            # to the receipt page for the existing order.
            monitoring_utils.set_custom_metric('payment_response_validation', 'redirect-to-receipt')
            return self.redirect_to_receipt_page(notification)
        except TransactionDeclined:
            # Declined transactions are the most common cause of errors during payment
            # processing and tend to be easy to correct (e.g., an incorrect CVV may have
            # been provided). The recovery path is not as clear for other exceptions,
            # so we let those drop through to the payment error page.
            order_number = request.POST.get('req_reference_number')
            old_basket_id = OrderNumberGenerator().basket_id(order_number)
            old_basket = Basket.objects.get(id=old_basket_id)

            new_basket = Basket.objects.create(owner=old_basket.owner, site=request.site)

            # We intentionally avoid thawing the old basket here to prevent order
            # numbers from being reused. For more, refer to commit a1efc68.
            new_basket.merge(old_basket, add_quantities=False)
            logger.info(
                'Created new basket [%d] from old basket [%d] for declined transaction.',
                new_basket.id,
                old_basket_id,
            )

            messages.error(self.request, _('transaction declined'), extra_tags='transaction-declined-message')

            monitoring_utils.set_custom_metric('payment_response_validation', 'redirect-to-payment-page')
            # TODO:
            # 1. There are sometimes messages from CyberSource that would make a more helpful message for users.
            # 2. We could have similar handling of other exceptions like UserCancelled and AuthorizationError

            redirect_url = get_payment_microfrontend_or_basket_url(self.request)
            return HttpResponseRedirect(redirect_url)

        except:  # pylint: disable=bare-except
            # logging handled by validate_notification, because not all exceptions are problematic
            monitoring_utils.set_custom_metric('payment_response_validation', 'redirect-to-error-page')
            return absolute_redirect(request, 'payment_error')

        try:
            order = self.create_order(request, basket, self._get_billing_address(notification))
            self.handle_post_order(order)
            return self.redirect_to_receipt_page(notification)
        except:  # pylint: disable=bare-except
            transaction_id, order_number, basket_id = self.get_ids_from_notification(notification)
            logger.exception(
                'Error processing order for transaction [%s], with order [%s] and basket [%d].',
                transaction_id,
                order_number,
                basket_id
            )
            return absolute_redirect(request, 'payment_error')

    def redirect_to_receipt_page(self, notification):
        receipt_page_url = get_receipt_page_url(
            self.request.site.siteconfiguration,
            order_number=notification.get('req_reference_number'),
            disable_back_button=True,
        )

        return redirect(receipt_page_url)


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

    def _get_billing_address(self, apple_pay_payment_contact):
        """ Converts ApplePayPaymentContact object to BillingAddress.

        See https://developer.apple.com/documentation/applepayjs/applepaypaymentcontact.
        """
        address_lines = apple_pay_payment_contact['addressLines']
        address_line_2 = address_lines[1] if len(address_lines) > 1 else ''
        country_code = apple_pay_payment_contact.get('countryCode')

        try:
            country = Country.objects.get(iso_3166_1_a2__iexact=country_code)
        except Country.DoesNotExist:
            logger.warning('Country matching code [%s] does not exist.', country_code)
            raise

        return BillingAddress(
            first_name=apple_pay_payment_contact['givenName'],
            last_name=apple_pay_payment_contact['familyName'],
            line1=address_lines[0],

            # Address line 2 is optional
            line2=address_line_2,

            # Oscar uses line4 for city
            line4=apple_pay_payment_contact['locality'],
            # Postal code is optional
            postcode=apple_pay_payment_contact.get('postalCode', ''),
            # State is optional
            state=apple_pay_payment_contact.get('administrativeArea', ''),
            country=country)

    def post(self, request):
        basket = request.basket

        if not request.data.get('token'):
            raise ValidationError({'error': 'token_missing'})

        try:
            billing_address = self._get_billing_address(request.data.get('billingContact'))
        except Exception:
            logger.exception(
                'Failed to authorize Apple Pay payment. An error occurred while parsing the billing address.')
            raise ValidationError({'error': 'billing_address_invalid'})

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
