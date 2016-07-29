""" Views for interacting with the Adyen payment processor. """
import json
import logging

from django.core.exceptions import MultipleObjectsReturned
from django.db import transaction
from django.http import HttpResponse, HttpResponseRedirect
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View
from oscar.apps.payment.exceptions import PaymentError, TransactionDeclined
from oscar.core.loading import get_class, get_model

from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.payment.exceptions import InvalidSignatureError
from ecommerce.payment_processors.adyen.processor import Adyen


logger = logging.getLogger(__name__)

NoShippingRequired = get_class('shipping.methods', 'NoShippingRequired')
OrderTotalCalculator = get_class('checkout.calculators', 'OrderTotalCalculator')
Source = get_model('payment', 'Source')


class AdyenNotificationView(EdxOrderPlacementMixin, View):
    @property
    def payment_processor(self):
        return Adyen()

    # Disable atomicity for the view. Otherwise, we'd be unable to commit to the database
    # until the request had concluded; Django will refuse to commit when an atomic() block
    # is active, since that would break atomicity. Without an order present in the database
    # at the time fulfillment is attempted, asynchronous order fulfillment tasks will fail.
    @method_decorator(transaction.non_atomic_requests)
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super(AdyenNotificationView, self).dispatch(request, *args, **kwargs)

    def post(self, request):
        request_body = json.loads(request.body)
        notification_items = request_body['notificationItems']
        for notification_item in notification_items:
            notification = notification_item['NotificationRequestItem']
            psp_reference = notification['pspReference']
            basket = None

            try:
                source = Source.objects.get(reference=psp_reference)
                basket = source.order.basket
            except Source.DoesNotExist:
                return HttpResponse(status=500)
            except MultipleObjectsReturned:
                return HttpResponse(status=500)
            finally:
                self.payment_processor.record_processor_response(
                    notification,
                    transaction_id=psp_reference,
                    basket=basket
                )

            self.payment_processor.handle_processor_response(notification, basket)

        # Adyen expects this response
        return HttpResponse('[accepted]')


class AdyenPaymentView(EdxOrderPlacementMixin, View):
    @property
    def payment_processor(self):
        return Adyen()

    # Disable atomicity for the view. Otherwise, we'd be unable to commit to the database
    # until the request had concluded; Django will refuse to commit when an atomic() block
    # is active, since that would break atomicity. Without an order present in the database
    # at the time fulfillment is attempted, asynchronous order fulfillment tasks will fail.
    @method_decorator(transaction.non_atomic_requests)
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super(AdyenPaymentView, self).dispatch(request, *args, **kwargs)

    def post(self, request):
        basket = request.basket
        transaction_id = None

        adyen_response = self.payment_processor.authorise(request.basket, request.POST['adyen-encrypted-data'])

        try:
            transaction_id = adyen_response.get('pspReference')
            order_number = basket.order_number

            logger.info(
                'Received Adyen authorization response for transaction [%s], associated with basket [%d].',
                transaction_id,
                basket.id
            )
        finally:
            # Store the response in the database regardless of its authenticity.
            ppr = self.payment_processor.record_processor_response(
                adyen_response,
                transaction_id=transaction_id,
                basket=basket
            )

        try:
            # Explicitly delimit operations which will be rolled back if an exception occurs.
            with transaction.atomic():
                try:
                    self.handle_payment(adyen_response, basket)
                except InvalidSignatureError:
                    logger.exception(
                        'Received an invalid Adyen response. The payment response was recorded in entry [%d].',
                        ppr.id
                    )
                    return HttpResponse(status=400)
                except TransactionDeclined as exception:
                    logger.info(
                        'Adyen payment did not complete for basket [%d] because [%s]. '
                        'The payment response was recorded in entry [%d].',
                        basket.id,
                        exception.__class__.__name__,
                        ppr.id
                    )
                    return HttpResponse()
                except PaymentError:
                    logger.exception(
                        'Adyen payment failed for basket [%d]. The payment response was recorded in entry [%d].',
                        basket.id,
                        ppr.id
                    )
                    return HttpResponse()
        except:  # pylint: disable=bare-except
            logger.exception('Attempts to handle payment for basket [%d] failed.', basket.id)
            return HttpResponse(status=500)

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

            self.handle_order_placement(
                order_number,
                user,
                basket,
                None,
                shipping_method,
                shipping_charge,
                None,
                order_total
            )

            return HttpResponseRedirect(
                '{}?orderNum={}'.format(self.payment_processor.receipt_page_url, basket.order_number)
            )
        except:  # pylint: disable=bare-except
            logger.exception(self.order_placement_failure_msg, basket.id)
            return HttpResponse(status=500)
