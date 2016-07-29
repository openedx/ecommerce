"""HTTP endpoints for interacting with refunds."""
from django.contrib.auth import get_user_model
from oscar.core.loading import get_model
from rest_framework import status, generics
from rest_framework.exceptions import ParseError
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from ecommerce.extensions.api import serializers
from ecommerce.extensions.api.exceptions import BadRequestException
from ecommerce.extensions.api.permissions import CanActForUser
from ecommerce.extensions.refund.api import find_orders_associated_with_course, create_refunds
from ecommerce.extensions.refund.status import REFUND


Refund = get_model('refund', 'Refund')
User = get_user_model()


class RefundCreateView(generics.CreateAPIView):
    """Creates refunds.

    Given a username and course ID, this view finds and creates a refund for each order
    matching the following criteria:

        * Order was placed by the User linked to username.
        * Order is in the COMPLETE state.
        * Order has at least one line item associated with the course ID.

    Note that only the line items associated with the course ID will be refunded.
    Items associated with a different course ID, or not associated with any course ID, will NOT be refunded.

    With the exception of superusers, users may only create refunds for themselves.
    Attempts to create refunds for other users will fail with HTTP 403.

    If refunds are created, a list of the refund IDs will be returned along with HTTP 201.
    If no refunds are created, HTTP 200 will be returned.
    """
    permission_classes = (IsAuthenticated, CanActForUser)

    def create(self, request, *args, **kwargs):
        """ Creates refunds, if eligible orders exist. """
        course_id = request.data.get('course_id')
        username = request.data.get('username')

        if not course_id:
            raise BadRequestException('No course_id specified.')

        # We should always have a username value as long as CanActForUser is in place.
        if not username:  # pragma: no cover
            raise BadRequestException('No username specified.')

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise BadRequestException('User "{}" does not exist.'.format(username))

        refunds = []

        # We can only create refunds if the user has orders.
        if user.orders.exists():
            orders = find_orders_associated_with_course(user, course_id)
            refunds = create_refunds(request.site, orders, course_id)

        # Return HTTP 201 if we created refunds.
        if refunds:
            refund_ids = [refund.id for refund in refunds]
            return Response(refund_ids, status=status.HTTP_201_CREATED)

        # Return HTTP 200 if we did NOT create refunds.
        return Response([], status=status.HTTP_200_OK)


class RefundProcessView(generics.UpdateAPIView):
    """Process--approve or deny--refunds.

    This view can be used to approve, or deny, a Refund. Under normal conditions, the view returns HTTP status 200
    and a serialized Refund. In the event of an error, the view will still return a serialized Refund (to reflect any
    changed statuses); however, HTTP status will be 500.

    Only staff users are permitted to use this view.
    """
    permission_classes = (IsAuthenticated, IsAdminUser,)
    queryset = Refund.objects.all()
    serializer_class = serializers.RefundSerializer

    def update(self, request, *args, **kwargs):
        APPROVE = 'approve'
        DENY = 'deny'
        APPROVE_PAYMENT_ONLY = 'approve_payment_only'

        action = request.data.get('action', '').lower()

        if action not in (APPROVE, DENY, APPROVE_PAYMENT_ONLY):
            raise ParseError('The action [{}] is not valid.'.format(action))

        refund = self.get_object()
        result = False

        if action in (APPROVE, APPROVE_PAYMENT_ONLY):
            revoke_fulfillment = action == APPROVE
            result = refund.approve(request.site, revoke_fulfillment=revoke_fulfillment)
        elif action == DENY:
            result = refund.deny()

        if result is None and refund.status in [REFUND.PENDING_WITH_REVOCATION, REFUND.PENDING_WITHOUT_REVOCATION]:
            result = True

        http_status = status.HTTP_200_OK if result else status.HTTP_500_INTERNAL_SERVER_ERROR
        serializer = self.get_serializer(refund)
        return Response(serializer.data, status=http_status)
