from __future__ import unicode_literals

import logging

import requests
import six
import waffle
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View
from oscar.apps.partner import strategy
from oscar.apps.payment.exceptions import GatewayError, PaymentError, TransactionDeclined, UserCancelled
from oscar.core.loading import get_class, get_model
from rest_framework import permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from ecommerce.extensions.api.serializers import OrderSerializer
from ecommerce.extensions.basket.utils import basket_add_organization_attribute
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.checkout.utils import get_receipt_page_url
from ecommerce.extensions.payment.exceptions import DuplicateReferenceNumber, InvalidBasketError, InvalidSignatureError
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


class CyberSourceProcessorMixin(object):
    @cached_property
    def payment_processor(self):
        return Cybersource(self.request.site)


class OrderCreationMixin(EdxOrderPlacementMixin):
    def create_order(self, request, basket, billing_address):
        try:
            # Note (CCB): In the future, if we do end up shipping physical products, we will need to
            # properly implement shipping methods. For more, see
            # http://django-oscar.readthedocs.org/en/latest/howto/how_to_configure_shipping.html.
            shipping_method = NoShippingRequired()
            shipping_charge = shipping_method.calculate(basket)

            # Note (CCB): This calculation assumes the payment processor has not sent a partial authorization,
            # thus we use the amounts stored in the database rather than those received from the payment processor.
            order_total = OrderTotalCalculator().calculate(basket, shipping_charge)
            user = basket.owner
            order_number = OrderNumberGenerator().order_number(basket)

            return self.handle_order_placement(
                order_number,
                user,
                basket,
                None,
                shipping_method,
                shipping_charge,
                billing_address,
                order_total,
                request=request
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.exception(self.order_placement_failure_msg, basket.id, e)
            raise


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
            'device_fingerprint_id': request.session.session_key,
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


class CybersourceNotificationMixin(CyberSourceProcessorMixin, OrderCreationMixin):
    # Disable atomicity for the view. Otherwise, we'd be unable to commit to the database
    # until the request had concluded; Django will refuse to commit when an atomic() block
    # is active, since that would break atomicity. Without an order present in the database
    # at the time fulfillment is attempted, asynchronous order fulfillment tasks will fail.
    @method_decorator(transaction.non_atomic_requests)
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super(CybersourceNotificationMixin, self).dispatch(request, *args, **kwargs)

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

    def _get_basket(self, basket_id):
        if not basket_id:
            return None

        try:
            basket_id = int(basket_id)
            basket = Basket.objects.get(id=basket_id)
            basket.strategy = strategy.Default()
            Applicator().apply(basket, basket.owner, self.request)
            return basket
        except (ValueError, ObjectDoesNotExist):
            return None

    def validate_notification(self, notification):
        # Note (CCB): Orders should not be created until the payment processor has validated the response's signature.
        # This validation is performed in the handle_payment method. After that method succeeds, the response can be
        # safely assumed to have originated from CyberSource.
        basket = None
        transaction_id = None

        try:
            transaction_id = notification.get('transaction_id')
            order_number = notification.get('req_reference_number')
            basket_id = OrderNumberGenerator().basket_id(order_number)

            logger.info(
                'Received CyberSource payment notification for transaction [%s], associated with basket [%d].',
                transaction_id,
                basket_id
            )

            basket = self._get_basket(basket_id)

            if not basket:
                logger.error('Received CyberSource payment notification for non-existent basket [%s].', basket_id)
                raise InvalidBasketError

            if basket.status != Basket.FROZEN:
                # We don't know how serious this situation is at this point, hence
                # the INFO level logging. This notification is most likely CyberSource
                # telling us that they've declined an attempt to pay for an existing order.
                logger.info(
                    'Received CyberSource payment notification for basket [%d] which is in a non-frozen state, [%s]',
                    basket.id, basket.status
                )
        finally:
            # Store the response in the database regardless of its authenticity.
            ppr = self.payment_processor.record_processor_response(
                notification, transaction_id=transaction_id, basket=basket
            )

        # Explicitly delimit operations which will be rolled back if an exception occurs.
        with transaction.atomic():
            try:
                self.handle_payment(notification, basket)
            except InvalidSignatureError:
                logger.exception(
                    'Received an invalid CyberSource response. The payment response was recorded in entry [%d].',
                    ppr.id
                )
                raise
            except (UserCancelled, TransactionDeclined) as exception:
                logger.info(
                    'CyberSource payment did not complete for basket [%d] because [%s]. '
                    'The payment response was recorded in entry [%d].',
                    basket.id,
                    exception.__class__.__name__,
                    ppr.id
                )
                raise
            except DuplicateReferenceNumber:
                if Order.objects.filter(number=order_number).exists() or PaymentProcessorResponse.objects.filter(
                        basket=basket).exclude(transaction_id__isnull=True).exclude(transaction_id='').exists():
                    logger.info(
                        'Received CyberSource payment notification for basket [%d] which is associated '
                        'with existing order [%s] or had an existing valid payment notification. '
                        'No payment was collected, and no new order will be created.',
                        basket.id,
                        order_number
                    )
                else:
                    logger.info(
                        'Received duplicate CyberSource payment notification for basket [%d] which is not associated '
                        'with any existing order (Missing Order Issue)',
                        basket.id,
                    )
                raise
            except PaymentError:
                logger.exception(
                    'CyberSource payment failed for basket [%d]. The payment response was recorded in entry [%d].',
                    basket.id,
                    ppr.id
                )
                raise
            except:  # pylint: disable=bare-except
                logger.exception('Attempts to handle payment for basket [%d] failed.', basket.id)
                raise

        return basket


class CybersourceInterstitialView(CybersourceNotificationMixin, View):
    """ Interstitial view for Cybersource Payments. """

    def post(self, request, *args, **kwargs):  # pylint: disable=unused-argument
        """Process a CyberSource merchant notification and place an order for paid products as appropriate."""
        try:
            notification = request.POST.dict()
            basket = self.validate_notification(notification)
        except DuplicateReferenceNumber:
            # CyberSource has told us that they've declined an attempt to pay
            # for an existing order. If this happens, we can redirect the browser
            # to the receipt page for the existing order.
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

            message = _(
                'An error occurred while processing your payment. You have not been charged. '
                'Please double-check the information you provided and try again. '
                'For help, {link_start}contact support{link_end}.'
            ).format(
                link_start='<a href="{}">'.format(request.site.siteconfiguration.payment_support_url),
                link_end='</a>',
            )

            messages.error(request, mark_safe(message))

            return redirect(reverse('basket:summary'))
        except:  # pylint: disable=bare-except
            return redirect(reverse('payment_error'))

        try:
            order = self.create_order(request, basket, self._get_billing_address(notification))
            self.handle_post_order(order)

            return self.redirect_to_receipt_page(notification)
        except:  # pylint: disable=bare-except
            return redirect(reverse('payment_error'))

    def redirect_to_receipt_page(self, notification):
        receipt_page_url = get_receipt_page_url(
            self.request.site.siteconfiguration,
            order_number=notification.get('req_reference_number')
        )

        return redirect(receipt_page_url)


class ApplePayStartSessionView(CyberSourceProcessorMixin, APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        url = request.data.get('url')

        if not url:
            raise ValidationError({'error': 'url is required'})

        data = {
            'merchantIdentifier': self.payment_processor.apple_pay_merchant_identifier,
            'domainName': request.site.domain,
            'displayName': request.site.name,
        }

        response = requests.post(url, json=data, cert=self.payment_processor.apple_pay_merchant_id_certificate_path)

        if response.status_code > 299:
            logger.warning('Failed to start Apple Pay session. [%s] returned status [%d] with content %s',
                           url, response.status_code, response.content)

        return JsonResponse(response.json(), status=response.status_code)


class CybersourceApplePayAuthorizationView(CyberSourceProcessorMixin, OrderCreationMixin, APIView):
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

        order = self.create_order(request, basket, billing_address)
        return Response(OrderSerializer(order, context={'request': request}).data, status=status.HTTP_201_CREATED)

    def handle_payment(self, response, basket):
        request = self.request
        basket = request.basket
        billing_address = self._get_billing_address(request.data.get('billingContact'))
        token = request.data['token']

        handled_processor_response = self.payment_processor.request_apple_pay_authorization(
            basket, billing_address, token)
        self.record_payment(basket, handled_processor_response)
