"""
Endpoints to facilitate retirement actions
"""

from edx_rest_framework_extensions.authentication import JwtAuthentication
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
    """
    authentication_classes = (JwtAuthentication, )
    permission_classes = (permissions.IsAuthenticated, permissions.IsAdminUser)

    def get(self, _, username):
        """
        Returns the ecommerce tracking id of the given LMS user, identified
        by username.
        """
        try:
            if not username:
                raise User.DoesNotExist()

            user = User.objects.get(username=username)
            return Response(
                {
                    'id': user.pk,
                    'ecommerce_tracking_id': ECOM_TRACKING_ID_FMT.format(user.pk)
                }
            )
        except User.DoesNotExist:
            return Response(
                status=status.HTTP_404_NOT_FOUND,
                data={'message': 'Invalid user.'}
            )
