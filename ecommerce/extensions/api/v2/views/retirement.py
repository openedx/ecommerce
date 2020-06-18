"""
Endpoints to facilitate retirement actions
"""
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from ecommerce.core.models import User
from ecommerce.extensions.analytics.utils import ECOM_TRACKING_ID_FMT


class EcommerceIdView(APIView):
    """
    Allows synchronization of the ecommerce user id and tracking id with
    other systems. Specifically this is used to retire users identified
    by "ecommerce-{id}" from Segment.

     Side effects:
        If the given user does not have an LMS user id, tries to find it. If found, adds the id to the user and
        saves the user. If the id cannot be found, writes custom metrics to record this fact.
    """
    authentication_classes = (JwtAuthentication,)
    permission_classes = (permissions.IsAuthenticated, permissions.IsAdminUser)

    def get(self, _, username):
        """
        Returns the old-style ecommerce tracking id (ecommerce-{id}) and the newer-style LMS user id of the given LMS
        user, identified by username.
        """
        try:
            if not username:
                raise User.DoesNotExist()

            user = User.objects.get(username=username)

            # If the user does not already have an LMS user id, add it. Note that we allow a missing LMS user id here
            # because this API only reads data from the db.
            called_from = u'retirement API'
            user.add_lms_user_id('ecommerce_missing_lms_user_id_retirement', called_from, allow_missing=True)

            return Response(
                {
                    'id': user.pk,
                    'ecommerce_tracking_id': ECOM_TRACKING_ID_FMT.format(user.pk),
                    'lms_user_id': user.lms_user_id_with_metric(usage='retirement API', allow_missing=True)
                }
            )
        except User.DoesNotExist:
            return Response(
                status=status.HTTP_404_NOT_FOUND,
                data={'message': 'Invalid user.'}
            )
