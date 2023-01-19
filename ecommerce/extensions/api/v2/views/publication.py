"""HTTP endpoints for course publication."""


from rest_framework import generics, status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from ecommerce.extensions.api import serializers
from ecommerce.extensions.api.throttles import ServiceUserThrottle
from ecommerce.extensions.partner.shortcuts import get_partner_for_site


class AtomicPublicationView(generics.CreateAPIView, generics.UpdateAPIView):
    """Attempt to save and publish a Course and associated products.

    If either fails, the entire operation is rolled back. This keeps Otto and the LMS in sync.
    """
    permission_classes = (IsAuthenticated, IsAdminUser,)
    serializer_class = serializers.AtomicPublicationSerializer
    throttle_classes = (ServiceUserThrottle,)

    def get_serializer_context(self):
        context = super(AtomicPublicationView, self).get_serializer_context()
        context['access_token'] = self.request.user.access_token if self.request else None
        context['partner'] = get_partner_for_site(self.request)
        return context

    def post(self, request, *args, **kwargs):
        return self._save_and_publish(request.data)

    def put(self, request, *_args, **kwargs):
        return self._save_and_publish(request.data, course_id=kwargs['course_id'])

    def _save_and_publish(self, data, course_id=None):
        """Create or update a Course and associated products, then publish the result."""
        if course_id is not None:
            data['id'] = course_id

        serializer = self.get_serializer(data=data)
        is_valid = serializer.is_valid(raise_exception=True)
        if not is_valid:
            return None

        created, failure, message = serializer.save()
        if failure:
            return Response({'error': message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        content = serializer.data
        content['message'] = message if message else None
        return Response(content, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
