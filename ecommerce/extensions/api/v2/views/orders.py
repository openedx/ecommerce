"""HTTP endpoints for interacting with orders."""
import logging

from oscar.core.loading import get_model, get_class
from rest_framework import status, generics
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response

from ecommerce.extensions.api import serializers
from ecommerce.extensions.api.constants import APIConstants as AC
from ecommerce.extensions.api.throttles import ServiceUserThrottle


logger = logging.getLogger(__name__)

Order = get_model('order', 'Order')


class OrderListView(generics.ListAPIView):
    """Endpoint for listing orders.

    Results are ordered with the newest order being the first in the list of results.
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.OrderSerializer

    def get_queryset(self):
        user = self.request.user
        qs = user.orders

        if user.is_superuser:
            qs = Order.objects.all()

        return qs.order_by('-date_placed')


class OrderRetrieveView(generics.RetrieveAPIView):
    """Allow the viewing of orders.

    Given an order number, allow the viewing of the corresponding order. This endpoint will return a 404 response
    status if no order is found. This endpoint will only return orders associated with the authenticated user.

    Returns:
        Order: The requested order.

    Example:
        >>> url = 'http://localhost:8002/api/v2/orders/100022'
        >>> headers = {
            'content-type': 'application/json',
            'Authorization': 'JWT '  token
        }
        >>> response = requests.get(url, headers=headers)
        >>> response.status_code
        200
        >>> response.content
        '{
            "currency": "USD",
            "date_placed": "2015-02-27T18:42:34.017218Z",
            "lines": [
                {
                    "description": "Seat in DemoX Course with Honor Certificate",
                    "status": "Complete",
                    "title": "Seat in DemoX Course with Honor Certificate",
                    "unit_price_excl_tax": 0.0
                }
            ],
            "number": "OSCR-100022",
            "status": "Complete",
            "total_excl_tax": 0.0
        }'
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.OrderSerializer
    lookup_field = AC.KEYS.ORDER_NUMBER

    def get_queryset(self):
        """Returns a queryset consisting of only the authenticated user's orders.

        This ensures we do not allow one user to view the data of another user.
        """
        return self.request.user.orders


class OrderByBasketRetrieveView(OrderRetrieveView):
    """Allow the viewing of Orders by Basket.

    Works exactly the same as OrderRetrieveView, except that orders are looked
    up via the id of the related basket.
    """
    lookup_field = 'basket_id'


class OrderFulfillView(generics.UpdateAPIView):
    permission_classes = (IsAuthenticated, DjangoModelPermissions,)
    throttle_classes = (ServiceUserThrottle,)
    lookup_field = 'number'
    queryset = Order.objects.all()
    serializer_class = serializers.OrderSerializer

    def update(self, request, *args, **kwargs):
        order = self.get_object()

        if not order.is_fulfillable:
            return Response(status=status.HTTP_406_NOT_ACCEPTABLE)

        logger.info('Attempting fulfillment of order [%s]...', order.number)
        post_checkout = get_class('checkout.signals', 'post_checkout')
        post_checkout.send(sender=post_checkout, order=order)

        if order.is_fulfillable:
            logger.warning('Fulfillment of order [%s] failed!', order.number)
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        serializer = self.get_serializer(order)
        return Response(serializer.data)
