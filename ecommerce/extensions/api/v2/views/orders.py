"""HTTP endpoints for interacting with orders."""
import logging

from oscar.core.loading import get_class, get_model
from rest_framework import filters, status, viewsets
from rest_framework.decorators import detail_route
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import DjangoModelPermissions, IsAuthenticated
from rest_framework.response import Response

from ecommerce.extensions.api import serializers
from ecommerce.extensions.api.filters import OrderFilter
from ecommerce.extensions.api.permissions import IsStaffOrOwner
from ecommerce.extensions.api.throttles import ServiceUserThrottle

logger = logging.getLogger(__name__)

Order = get_model('order', 'Order')
post_checkout = get_class('checkout.signals', 'post_checkout')


class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    lookup_field = 'number'
    permission_classes = (IsAuthenticated, IsStaffOrOwner, DjangoModelPermissions,)
    queryset = Order.objects.all()
    serializer_class = serializers.OrderSerializer
    throttle_classes = (ServiceUserThrottle,)
    filter_backends = (filters.DjangoFilterBackend,)
    filter_class = OrderFilter

    def filter_queryset(self, queryset):
        queryset = super(OrderViewSet, self).filter_queryset(queryset)

        username = self.request.query_params.get('username')
        user = self.request.user

        # Non-staff users should only see their own orders
        if not user.is_staff:
            if username and user.username != username:
                raise PermissionDenied

            queryset = queryset.filter(user=user)

        return queryset.filter(partner=self.request.site.siteconfiguration.partner)

    @detail_route(methods=['put', 'patch'])
    def fulfill(self, request, number=None):  # pylint: disable=unused-argument
        """ Fulfill order """
        order = self.get_object()

        if not order.is_fulfillable:
            return Response(status=status.HTTP_406_NOT_ACCEPTABLE)

        # Get email_opt_in from the query parameters if it exists, defaulting to false
        email_opt_in = request.query_params.get('email_opt_in', False) == 'True'

        logger.info('Attempting fulfillment of order [%s]...', order.number)
        post_checkout.send(sender=post_checkout, order=order, request=request, email_opt_in=email_opt_in)

        if order.is_fulfillable:
            logger.warning('Fulfillment of order [%s] failed!', order.number)
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        serializer = self.get_serializer(order)
        return Response(serializer.data)
