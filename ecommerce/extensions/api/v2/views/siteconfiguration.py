"""API endpoint for site configuration."""
from rest_framework import viewsets
from rest_framework.permissions import IsAdminUser, IsAuthenticated

from ecommerce.core.models import SiteConfiguration
from ecommerce.extensions.api import serializers


class SiteConfigurationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SiteConfiguration.objects.all()
    serializer_class = serializers.SiteConfigurationSerializer
    permission_classes = (IsAuthenticated, IsAdminUser,)
