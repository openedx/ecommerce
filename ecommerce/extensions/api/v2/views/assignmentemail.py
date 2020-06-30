"""API endpoint for sending assignment emails to Learners"""


import logging

from django.conf import settings
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from sailthru.sailthru_client import SailthruClient

from ecommerce.extensions.api.permissions import IsStaffOrOwner
from ecommerce.extensions.api.throttles import ServiceUserThrottle
from ecommerce.extensions.offer.constants import (
    OFFER_ASSIGNED,
    OFFER_ASSIGNMENT_EMAIL_BOUNCED,
    OFFER_ASSIGNMENT_EMAIL_PENDING
)
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
            Message identifier received from Sailthru
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


class AssignmentEmailBounce(APIView):
    """
    Receive Sailthru bounce-api POST.
    Please refer to https://getstarted.sailthru.com/developers/api-basics/postbacks/
    """
    permission_classes = ()
    authentication_classes = ()

    def update_email_status(self, send_id):
        """Update the OfferAssignment model"""
        offer = OfferAssignmentEmailAttempt.objects.get(send_id=send_id)
        assigned_offer = OfferAssignment.objects.get(id=offer.offer_assignment.id)
        with transaction.atomic():
            OfferAssignment.objects.select_for_update().filter(
                user_email=assigned_offer.user_email,
                code=assigned_offer.code,
                status=OFFER_ASSIGNED
            ).update(status=OFFER_ASSIGNMENT_EMAIL_BOUNCED)

    def post(self, request):
        """
        POST /ecommerce/api/v2/assignment-email/bounce
        Requires a JSON object of the following format:
        {
            'email': blashsdsd@dfsdf.com
            'send_id': WFQKQW5K3LBgi0mk
            'action': hardbounce
            'api_key': 6b805755ce5a23e3c0459aaa598efc56
            'sig': 13b3987b656c7771fcac92982fdfb331
        }
        Returns HTTP_200_OK

        Keys:
        *email*
            Email of the customer whose email bounced.
        *send_id*
            The unique identifier of the bounced message.
        *action*
            hardbounce: Email bounced.
        *api_key*
            Key provided by Sailthru.
        *sig*
            Hash of API key and all parameter values for the postback call
        """
        secret = settings.SAILTHRU_SECRET
        key = settings.SAILTHRU_KEY
        if secret and key:
            sailthru_client = SailthruClient(key, secret)
            send_id = request.data.get('send_id')
            email = request.data.get('email')
            sig = request.data.get('sig')
            api_key = request.data.get('api_key')
            if sailthru_client.receive_hardbounce_post(request.data):
                try:
                    self.update_email_status(send_id)
                except (OfferAssignment.DoesNotExist, OfferAssignmentEmailAttempt.DoesNotExist):
                    # Note: Marketing email bounces also come through this code path and
                    # its expected that they would not have a corresponding OfferAssignment
                    pass
            else:
                logger.error('[Offer Assignment] AssignmentEmailBounce: Bounce message could not be verified. '
                             'send_id: %s, email: %s, sig: %s, api_key_sailthru: %s, api_key_local: %s ',
                             send_id, email, sig, api_key, key)
        else:
            logger.error('[Offer Assignment] AssignmentEmailBounce: SAILTHRU Parameters not found')
        return Response({}, status=status.HTTP_200_OK)
