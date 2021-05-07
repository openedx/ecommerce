"""API endpoint for sending assignment emails to Learners"""


import logging

from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ecommerce.extensions.api.permissions import IsStaffOrOwner
from ecommerce.extensions.api.throttles import ServiceUserThrottle
from ecommerce.extensions.offer.constants import OFFER_ASSIGNED, OFFER_ASSIGNMENT_EMAIL_PENDING
from ecommerce.extensions.offer.models import OfferAssignment, OfferAssignmentEmailAttempt

logger = logging.getLogger(__name__)


class OfferAssignmentEmailStatus:
    """
    Offer assignment email status enumeration
    """
    SUCCESS = 'success'
    UPDATED = 'updated'
    FAILED = 'failed'


class AssignmentEmailStatus(APIView):
    """
    This api is called from ecommerce-worker to update assignment email status
    in OfferAssignment and OfferAssignmentEmailAttempt model.
    """
    permission_classes = (IsAuthenticated, IsStaffOrOwner,)
    throttle_classes = (ServiceUserThrottle,)

    def update_email_status(self, offer_assignment_id, send_id):
        """Update the OfferAssignment and OfferAssignmentEmailAttempt model"""
        assigned_offer = OfferAssignment.objects.get(id=offer_assignment_id)
        with transaction.atomic():
            OfferAssignment.objects.select_for_update().filter(
                user_email=assigned_offer.user_email,
                code=assigned_offer.code,
                status=OFFER_ASSIGNMENT_EMAIL_PENDING
            ).update(status=OFFER_ASSIGNED)
            OfferAssignmentEmailAttempt.objects.create(offer_assignment=assigned_offer, send_id=send_id)

    def post(self, request):
        """
        POST request handler for /ecommerce/api/v2/assignment-email/status
        POST /ecommerce/api/v2/assignment-email/status
        Requires a JSON object of the following format:
       {
            'offer_assignment_id': 555,
            'send_id': 'XBEn85WnoQJsIhk6'
            'status': 'success'
        }
        Returns a JSON object of the following format:
       {
            'offer_assignment_id': 555,
            'send_id': 'XBEn85WnoQJsIhk6'
            'status': 'updated'
            'error': ''
        }
        Keys:
        *offer_assignment_id*
            Primary key of the entry in the OfferAssignment model.
        *send_id*
            Message identifier received from ecommerce-worker
        *status*
            The OfferAssignment model update status
        *error*
            Error detail. Empty on a successful update.
        """
        offer_assignment_id = request.data.get('offer_assignment_id')
        send_id = request.data.get('send_id')
        email_status = request.data.get('status')
        update_status = {
            'offer_assignment_id': offer_assignment_id,
            'send_id': send_id,
        }
        extra_status = {}
        if email_status == OfferAssignmentEmailStatus.SUCCESS:
            try:
                self.update_email_status(offer_assignment_id, send_id)
                extra_status = {
                    'status': OfferAssignmentEmailStatus.UPDATED,
                    'error': ''
                }
            except OfferAssignment.DoesNotExist as exc:
                logger.exception('[Offer Assignment] AssignmentEmailStatus update raised: %r', exc)
                extra_status = {
                    'status': OfferAssignmentEmailStatus.FAILED,
                    'error': str(exc)
                }
                update_status.update(extra_status)
                return Response(update_status, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            logger.error(
                '[Offer Assignment] AssignmentEmailStatus could not update status for OfferAssignmentId: %d',
                offer_assignment_id)
            extra_status = {
                'status': OfferAssignmentEmailStatus.FAILED,
                'error': 'Incorrect status'
            }
            update_status.update(extra_status)
            return Response(update_status, status=status.HTTP_400_BAD_REQUEST)
        update_status.update(extra_status)
        return Response(update_status, status=status.HTTP_200_OK)
