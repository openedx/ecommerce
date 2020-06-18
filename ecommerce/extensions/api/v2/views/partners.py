"""HTTP endpoints for interacting with partners."""


from oscar.core.loading import get_model
from rest_framework import viewsets
from rest_framework.permissions import IsAdminUser, IsAuthenticated

from ecommerce.extensions.api import serializers

Partner = get_model('partner', 'Partner')


class PartnerViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Partner.objects.all()
    serializer_class = serializers.PartnerSerializer
    permission_classes = (IsAuthenticated, IsAdminUser,)
