""" Views for interacting with the payment processor. """
from django.conf import settings
from django.http import HttpResponse
from django.views.generic import View
from oscar.apps.checkout.mixins import OrderPlacementMixin
from oscar.apps.payment.models import SourceType
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from ecommerce.extensions.order.models import Order
from ecommerce.extensions.fulfillment.status import ORDER
from ecommerce.extensions.fulfillment.mixins import FulfillmentMixin
from ecommerce.extensions.payment.constants import ProcessorConstants as PC
from ecommerce.extensions.payment.helpers import get_processor_class
from ecommerce.extensions.payment.serializers import ProcessorSerializer


class ProcessorListView(ListAPIView):
    """ View that lists the available payment processors. """
    pagination_class = None
    permission_classes = (IsAuthenticated,)
    serializer_class = ProcessorSerializer

    def get_queryset(self):
        """ Fetch the list of payment processor classes based on django settings."""
        return [get_processor_class(path) for path in settings.PAYMENT_PROCESSORS]


class CybersourceResponseView(View, OrderPlacementMixin, FulfillmentMixin):
    """
    Accept response from the processor and fulfill the request
    """

    def post(self, request):
        """ Handle the response we've been given from the processor. """
        payment_processor = get_processor_class(settings.PAYMENT_PROCESSORS[0])
        # check the data we get
        params = request.POST.dict()
        result = payment_processor().handle_processor_response(params)
        if result[PC.SUCCESS]:
            # get the order
            order = Order.objects.get(number=result[PC.ORDER_NUMBER])
            # register the money in Oscar
            self._register_payment(order, payment_processor.NAME)
            # fulfill the order
            self._fulfill_order(order)

        # It doesn't matter how we respond to the payment processor if the
        # payment failed.
        return HttpResponse()

    def _register_payment(self, order, processor_name):
        """
        Records the payment source and event and updates the order status

        Args:
            order (Order): the order that is being paid for
            processor_name (str): the name of the processor that will be processing this payment
        Returns:
            None
        """

        # get the source
        source_type, _ = SourceType.objects.get_or_create(name=processor_name)
        source = source_type.sources.model(
            source_type=source_type, amount_allocated=order.total_excl_tax, currency=order.currency
        )

        # record payment events
        self.add_payment_source(source)
        self.add_payment_event(PC.PAID_EVENT_NAME, order.total_excl_tax, order.number)
        self.save_payment_details(order)

        # update the status of the order
        order.set_status(ORDER.PAID)
