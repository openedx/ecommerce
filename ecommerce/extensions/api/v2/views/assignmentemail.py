"""API endpoint for sending assignment emails to Learners"""
import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ecommerce.extensions.api.permissions import IsStaffOrOwner
from ecommerce.extensions.offer.constants import OFFER_ASSIGNED, OFFER_ASSIGNMENT_EMAIL_BOUNCED
from ecommerce.extensions.offer.models import OfferAssignment, OfferAssignmentEmailAttempt

logger = logging.getLogger(__name__)


class AssignmentEmail(APIView):
    """Coupon code assignment email related functions"""
    permission_classes = (IsAuthenticated,)

    def get(self, request):  # pylint: disable=unused-argument
        """
        Retrieve the default email template
        GET /ecommerce/api/v2/assignmentemail/template
        Returns a JSON response of the following format:
        {'template': ('Your learning manager has provided you with a new access code to take a course at edX.'
                     ' You may redeem this code for {code_usage_count} courses. '

                     'edX login: {user_email}'
                     'Enrollment url: {enrollment_url}'
                     'Access Code: {code}'
                     'Expiration date: {code_expiration_date}'

                     'You may go directly to the Enrollment URL to view courses that are available for this code'
                     ' or you can insert the access code at check out under "coupon code" for applicable courses.'

                     'For any questions, please reach out to your Learning Manager.')}
        """
        email_template = ('Your learning manager has provided you with a new access code to take a course at edX.'
                          ' You may redeem this code for {code_usage_count} courses. '

                          'edX login: {user_email}'
                          'Enrollment url: {enrollment_url}'
                          'Access Code: {code}'
                          'Expiration date: {code_expiration_date}'

                          'You may go directly to the Enrollment URL to view courses that are available for this code'
                          ' or you can insert the access code at check out under "coupon code" for applicable courses.'

                          'For any questions, please reach out to your Learning Manager.')

        return Response(
            status=status.HTTP_200_OK,
            data={'template': email_template}
        )


class AssignmentEmailStatus(APIView):
    """
    This api is called from ecommerce-worker to update assignment email status
    in offer_assignment and offer_assignment_email model.
    """
    permission_classes = (IsAuthenticated, IsStaffOrOwner,)

    def update_email_status(self, offer_assignment_id, send_id):
        """Update the OfferAssignment and OfferAssignmentEmailAttempt model"""
        assigned_offer = OfferAssignment.objects.get(id=offer_assignment_id)
        assigned_offer.status = OFFER_ASSIGNED
        assigned_offer.save(update_fields=['status'])
        OfferAssignmentEmailAttempt.objects.create(offer_assignment=assigned_offer, send_id=send_id)

    def post(self, request):
        """
        POST /ecommerce/api/v2/assignmentemail/updatestatus
        Requires a JSON object of the following format:
       {
            'offer_id': '555',
            'send_id': 'XBEn85WnoQJsIhk6'
            'status': 'success'
        }
        Returns a JSON object of the following format:
       {
            'offer_id': '555',
            'send_id': 'XBEn85WnoQJsIhk6'
            'status': 'updated'
            'error': ''
        }
        Keys:
        *offer_id*
            Primary key of the entry in the offer_assignment model.
        *status*
            The offer_assignment model update status
        *error*
            Error detail. Empty on a successful update.
        """
        offer_assignment_id = int(request.data.get('offer_id'))
        send_id = request.data.get('send_id')
        email_status = request.data.get('status')
        update_status = {
            'offer_id': offer_assignment_id,
            'send_id': send_id,
        }
        extra_status = {}
        if email_status == 'success':
            try:
                self.update_email_status(offer_assignment_id, send_id)
                extra_status = {
                    'status': 'updated',
                    'error': ''
                }
            except OfferAssignment.DoesNotExist as exc:
                logger.exception('[Offer Assignment] AssignmentEmailStatus update raised: %r', exc)
                extra_status = {
                    'status': 'failed',
                    'error': str(exc)
                }
        update_status.update(extra_status)
        return Response(update_status, status=status.HTTP_200_OK)


class AssignmentEmailBounce(APIView):
    """Receive Sailthru bounce-api POST"""
    # Note: Will use a proxy api to secure this endpoint
    permission_classes = ()
    authentication_classes = ()

    def update_email_status(self, send_id):
        """Update the OfferAssignment model"""
        offer = OfferAssignmentEmailAttempt.objects.get(send_id=send_id)
        assigned_offer = OfferAssignment.objects.get(id=offer.offer_assignment.id)
        assigned_offer.status = OFFER_ASSIGNMENT_EMAIL_BOUNCED
        assigned_offer.save(update_fields=['status'])

    def post(self, request):
        """
        POST /ecommerce/api/v2/assignmentemail/receivebounce
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
        try:
            self.update_email_status(send_id)
        except (OfferAssignment.DoesNotExist, OfferAssignmentEmailAttempt.DoesNotExist) as exc:
            logger.exception('[Offer Assignment] AssignmentEmailBounce could not update status and raised: %r', exc)
        return Response({}, status=status.HTTP_200_OK)
