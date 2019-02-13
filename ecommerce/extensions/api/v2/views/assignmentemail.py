"""API endpoint for sending assignment emails to Learners"""
import hashlib
import json
import logging


from django.conf import settings
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ecommerce.extensions.api.permissions import IsStaffOrOwner
from ecommerce.extensions.offer.constants import OFFER_ASSIGNED, OFFER_ASSIGNMENT_EMAIL_BOUNCED
from ecommerce.extensions.offer.models import OfferAssignment, OfferAssignmentEmailAttempt

logger = logging.getLogger(__name__)


class OfferAssignmentEmailStatus(object):
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

    def update_email_status(self, offer_assignment_id, send_id):
        """Update the OfferAssignment and OfferAssignmentEmailAttempt model"""
        assigned_offer = OfferAssignment.objects.get(id=offer_assignment_id)
        with transaction.atomic():
            OfferAssignment.objects.select_for_update().filter(
                user_email=assigned_offer.user_email,
                code=assigned_offer.code
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
                code=assigned_offer.code
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
        send_id = request.data.get('send_id')
        received_data = {
            'email': request.data.get('email'),
            'send_id': send_id,
            'action': request.data.get('action')
        }
        received_hash = request.data.get('sig')
        sailthru_secret = settings.SAILTHRU_SECRET
        sailthru_key = settings.SAILTHRU_KEY
        if sailthru_secret and sailthru_key:
            hash_string = sailthru_secret + sailthru_key + 'json' + json.dumps(received_data)
            computed_hash = hashlib.md5(hash_string).hexdigest()
            if computed_hash == received_hash:
                try:
                    self.update_email_status(send_id)
                except (OfferAssignment.DoesNotExist, OfferAssignmentEmailAttempt.DoesNotExist) as exc:
                    logger.exception(
                        '[Offer Assignment] AssignmentEmailBounce could not update status and raised: %r', exc)
                    return Response({}, status=status.HTTP_400_BAD_REQUEST)
            else:
                logger.error('[Offer Assignment] AssignmentEmailBounce: Message hash does not match the '
                             'computed hash. Received hash: %s, Computed hash: %s', received_hash, computed_hash)
                return Response({}, status=status.HTTP_400_BAD_REQUEST)
        else:
            logger.error('[Offer Assignment] AssignmentEmailBounce: SAILTHRU Parameters not found')
        return Response({}, status=status.HTTP_200_OK)
